import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.connected_source import (
    ConnectedSource,
    ConnectedSourceGitHubTarget,
    ConnectedSourceStatus,
)
from app.db.models.integration import Integration, IntegrationStatus, IntegrationType
from app.db.models.partner_update import (
    PartnerUpdate,
    PartnerUpdateSourceType,
    PartnerUpdateStatus,
)
from app.db.models.source_event import SourceEvent, SourcePayload
from app.domains.admin.integrations.secrets import get_integration_secret_value
from app.domains.source_events.schemas import SourceEventIngestRequest
from app.domains.source_events.service import SourceEventQueueService
from app.domains.webhooks.github.security import verify_github_signature

MEANINGFUL_GITHUB_EVENTS = {
    "issues",
    "issue_comment",
    "pull_request",
    "pull_request_review",
    "pull_request_review_comment",
    "push",
    "release",
}
IGNORED_GITHUB_ACTIONS = {
    "deleted",
    "transferred",
}
MEANINGFUL_GITHUB_ACTIONS = {
    "assigned",
    "closed",
    "converted_to_draft",
    "created",
    "edited",
    "labeled",
    "opened",
    "published",
    "ready_for_review",
    "reopened",
    "review_requested",
    "submitted",
    "synchronize",
    "unassigned",
    "unlabeled",
}
WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class GitHubTargetCandidate:
    target_kind: str
    repository: str
    number: int | None
    external_identifier: str
    source_url: str | None


class GitHubWebhookService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def handle_event_payload(
        self,
        *,
        raw_body: bytes,
        signature: str | None,
        event_name: str | None,
        delivery_id: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        webhook_secret = await self._get_enabled_webhook_secret()
        if not verify_github_signature(
            webhook_secret=webhook_secret,
            raw_body=raw_body,
            signature=signature,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid GitHub signature.",
            )

        event_type = clean_optional(event_name) or clean_optional(payload.get("event")) or "unknown"
        if event_type == "ping":
            return {"status": "ignored", "reason": "GitHub ping event acknowledged."}

        candidates = github_target_candidates(event_type, payload)
        if not candidates:
            return {
                "status": "ignored",
                "reason": "GitHub payload did not include a supported repository, issue, or PR.",
            }

        sources = await self._load_active_github_sources(candidates)
        if not sources:
            return {
                "status": "ignored",
                "reason": "No active GitHub connected source is mapped to this event.",
            }

        results = []
        for source, github_target, candidate in sources:
            results.append(
                await self._process_for_source(
                    source=source,
                    github_target=github_target,
                    candidate=candidate,
                    event_type=event_type,
                    delivery_id=delivery_id,
                    payload=payload,
                )
            )

        processed_count = sum(1 for item in results if item.get("status") == "processed")
        duplicate_count = sum(1 for item in results if item.get("status") == "duplicate")
        ignored_count = sum(1 for item in results if item.get("status") == "ignored")
        return {
            "status": "processed" if processed_count else "ignored",
            "processed_count": processed_count,
            "duplicate_count": duplicate_count,
            "ignored_count": ignored_count,
            "results": results,
        }

    async def _process_for_source(
        self,
        *,
        source: ConnectedSource,
        github_target: ConnectedSourceGitHubTarget,
        candidate: GitHubTargetCandidate,
        event_type: str,
        delivery_id: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        event_timestamp = github_event_timestamp(payload)
        event_id = github_event_id(
            source=source,
            event_type=event_type,
            delivery_id=delivery_id,
            payload=payload,
        )
        queued = await SourceEventQueueService(self.db).enqueue_event(
            SourceEventIngestRequest(
                connected_source_id=source.connected_source_id,
                external_event_id=event_id,
                idempotency_key=f"github:{event_id}",
                source_url=github_target.target_url,
                source_event_timestamp=event_timestamp,
                technical_metadata=github_technical_metadata(
                    event_type=event_type,
                    candidate=candidate,
                    payload=payload,
                    sender_hash=self._hash_sender(github_sender_login(payload)),
                ),
                raw_payload_json=None,
                raw_text_encrypted=None,
                retention_policy="technical_metadata_only",
            )
        )

        if queued.is_duplicate:
            return {
                "status": "duplicate",
                "source_event_id": str(queued.source_event.source_event_id),
            }

        processing = await SourceEventQueueService(self.db).process_event(
            queued.source_event.source_event_id,
            handler=GitHubSourceEventProcessor(
                db=self.db,
                payload=payload,
                event_type=event_type,
                github_target=github_target,
            ).process,
        )
        return {
            "status": "processed",
            "source_event_id": str(queued.source_event.source_event_id),
            "processing_status": processing.status.value if processing.status is not None else None,
            "message": processing.message,
        }

    async def _get_enabled_webhook_secret(self) -> str:
        result = await self.db.execute(
            select(Integration).where(Integration.integration_type == IntegrationType.github.value)
        )
        integration = result.scalar_one_or_none()
        if integration is None or integration.status != IntegrationStatus.enabled.value:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GitHub global integration is not enabled.",
            )

        webhook_secret = await get_integration_secret_value(
            self.db,
            self.settings,
            integration_type=IntegrationType.github,
            secret_name="webhook_secret",
        )
        if webhook_secret is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GitHub webhook secret is not configured.",
            )
        return webhook_secret

    async def _load_active_github_sources(
        self,
        candidates: list[GitHubTargetCandidate],
    ) -> list[tuple[ConnectedSource, ConnectedSourceGitHubTarget, GitHubTargetCandidate]]:
        candidates_by_identifier = {
            candidate.external_identifier: candidate for candidate in candidates
        }
        result = await self.db.execute(
            select(ConnectedSource, ConnectedSourceGitHubTarget)
            .join(
                ConnectedSourceGitHubTarget,
                ConnectedSourceGitHubTarget.connected_source_id
                == ConnectedSource.connected_source_id,
            )
            .where(ConnectedSource.status == ConnectedSourceStatus.active.value)
            .where(ConnectedSource.external_identifier.in_(candidates_by_identifier))
        )
        matches = []
        for source, github_target in result.all():
            candidate = candidates_by_identifier.get(source.external_identifier)
            if candidate is not None:
                matches.append((source, github_target, candidate))
        return matches

    def _hash_sender(self, sender_login: str | None) -> str | None:
        if sender_login is None:
            return None
        return hmac.new(
            self.settings.app_secret_key.encode(),
            sender_login.encode(),
            hashlib.sha256,
        ).hexdigest()


class GitHubSourceEventProcessor:
    def __init__(
        self,
        *,
        db: AsyncSession,
        payload: dict[str, Any],
        event_type: str,
        github_target: ConnectedSourceGitHubTarget,
    ) -> None:
        self.db = db
        self.payload = payload
        self.event_type = event_type
        self.github_target = github_target

    async def process(
        self,
        source_event: SourceEvent,
        _payload: SourcePayload | None,
    ) -> dict[str, Any]:
        if not is_meaningful_github_event(self.event_type, self.payload):
            return {
                "pending_updates_created": 0,
                "reason": "GitHub event did not meet the developer-owned rule.",
            }

        existing_update = await self._find_existing_update(source_event.idempotency_key)
        if existing_update is not None:
            return {
                "pending_updates_created": 0,
                "reason": "Pending update already exists for this GitHub event.",
                "update_id": str(existing_update.update_id),
            }

        label = github_source_label(self.github_target)
        update = PartnerUpdate(
            partner_id=source_event.partner_id,
            cycle_month=source_event.source_event_timestamp.date().replace(day=1),
            title=github_update_title(
                event_type=self.event_type,
                github_target=self.github_target,
                payload=self.payload,
            ),
            summary=github_update_summary(
                event_type=self.event_type,
                github_target=self.github_target,
                payload=self.payload,
            ),
            source_type=PartnerUpdateSourceType.github.value,
            source_label=label,
            source_url=source_event.source_url,
            source_event_key=source_event.idempotency_key,
            connected_source_id=source_event.connected_source_id,
            source_event_id=source_event.source_event_id,
            status=PartnerUpdateStatus.pending.value,
            created_by=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.db.add(update)
        await self.db.flush()
        return {
            "pending_updates_created": 1,
            "update_id": str(update.update_id),
        }

    async def _find_existing_update(self, source_event_key: str) -> PartnerUpdate | None:
        result = await self.db.execute(
            select(PartnerUpdate).where(PartnerUpdate.source_event_key == source_event_key)
        )
        return result.scalar_one_or_none()


def github_target_candidates(
    event_type: str,
    payload: dict[str, Any],
) -> list[GitHubTargetCandidate]:
    repository = github_repository(payload)
    repository_url = github_repository_url(payload)
    if repository is None:
        return []

    candidates = [
        GitHubTargetCandidate(
            target_kind="repository",
            repository=repository,
            number=None,
            external_identifier=f"github:repository:{repository.lower()}",
            source_url=repository_url,
        )
    ]

    issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
    pull_request = (
        payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else {}
    )
    if event_type in {"issues", "issue_comment"} and issue:
        number = int(issue.get("number")) if issue.get("number") else None
        if number is not None:
            is_pull_request = isinstance(issue.get("pull_request"), dict)
            target_kind = "pull_request" if is_pull_request else "issue"
            candidates.insert(
                0,
                GitHubTargetCandidate(
                    target_kind=target_kind,
                    repository=repository,
                    number=number,
                    external_identifier=f"github:{target_kind}:{repository.lower()}:{number}",
                    source_url=clean_optional(issue.get("html_url")),
                ),
            )

    if event_type.startswith("pull_request") and pull_request:
        number = int(pull_request.get("number")) if pull_request.get("number") else None
        if number is not None:
            candidates.insert(
                0,
                GitHubTargetCandidate(
                    target_kind="pull_request",
                    repository=repository,
                    number=number,
                    external_identifier=f"github:pull_request:{repository.lower()}:{number}",
                    source_url=clean_optional(pull_request.get("html_url")),
                ),
            )

    deduped: dict[str, GitHubTargetCandidate] = {}
    for candidate in candidates:
        deduped[candidate.external_identifier] = candidate
    return list(deduped.values())


def github_repository(payload: dict[str, Any]) -> str | None:
    repository = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    full_name = clean_optional(repository.get("full_name"))
    if full_name:
        return full_name
    owner = repository.get("owner") if isinstance(repository.get("owner"), dict) else {}
    owner_login = clean_optional(owner.get("login"))
    repo_name = clean_optional(repository.get("name"))
    if owner_login and repo_name:
        return f"{owner_login}/{repo_name}"
    return None


def github_repository_url(payload: dict[str, Any]) -> str | None:
    repository = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    return clean_optional(repository.get("html_url"))


def github_event_timestamp(payload: dict[str, Any]) -> datetime:
    candidates = [
        nested_text(payload, "head_commit", "timestamp"),
        nested_text(payload, "issue", "updated_at"),
        nested_text(payload, "pull_request", "updated_at"),
        nested_text(payload, "release", "published_at"),
        clean_optional(payload.get("created_at")),
        clean_optional(payload.get("updated_at")),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            continue
    return datetime.now(UTC)


def github_event_id(
    *,
    source: ConnectedSource,
    event_type: str,
    delivery_id: str | None,
    payload: dict[str, Any],
) -> str:
    action = clean_optional(payload.get("action")) or "none"
    event_identity = ":".join(
        [
            str(source.connected_source_id),
            clean_optional(delivery_id) or "no-delivery",
            event_type,
            action,
            source.external_identifier or "unknown-target",
        ]
    )
    return hashlib.sha256(event_identity.encode()).hexdigest()


def github_technical_metadata(
    *,
    event_type: str,
    candidate: GitHubTargetCandidate,
    payload: dict[str, Any],
    sender_hash: str | None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "action": clean_optional(payload.get("action")),
        "target_kind": candidate.target_kind,
        "repository": candidate.repository,
        "number": candidate.number,
        "sender_hash": sender_hash,
    }


def is_meaningful_github_event(event_type: str, payload: dict[str, Any]) -> bool:
    if event_type not in MEANINGFUL_GITHUB_EVENTS:
        return False
    if event_type == "push":
        return bool(payload.get("commits") or payload.get("head_commit"))

    action = clean_optional(payload.get("action"))
    if action is None:
        return event_type in {"issue_comment", "pull_request_review_comment"}
    if action in IGNORED_GITHUB_ACTIONS:
        return False
    return action in MEANINGFUL_GITHUB_ACTIONS


def github_source_label(github_target: ConnectedSourceGitHubTarget) -> str:
    if github_target.target_kind == "repository":
        return github_target.repository or "GitHub repository"
    prefix = "PR" if github_target.target_kind == "pull_request" else "Issue"
    return f"{github_target.repository} {prefix} #{github_target.number}"[:240]


def github_update_title(
    *,
    event_type: str,
    github_target: ConnectedSourceGitHubTarget,
    payload: dict[str, Any],
) -> str:
    action = clean_optional(payload.get("action")) or "updated"
    label = github_source_label(github_target)
    if event_type == "push":
        return f"GitHub push update: {label}"[:300]
    return f"GitHub {event_type.replace('_', ' ')} {action}: {label}"[:300]


def github_update_summary(
    *,
    event_type: str,
    github_target: ConnectedSourceGitHubTarget,
    payload: dict[str, Any],
) -> str:
    if event_type == "push":
        commits = payload.get("commits")
        commit_count = len(commits) if isinstance(commits, list) else 0
        ref = clean_optional(payload.get("ref"))
        branch = ref.rsplit("/", 1)[-1] if ref else None
        return summarize_text(
            f"{github_source_label(github_target)} received {commit_count} commit(s)"
            f"{f' on {branch}' if branch else ''}."
        )

    title = github_content_title(payload) or github_source_label(github_target)
    action = clean_optional(payload.get("action")) or "updated"
    body = github_content_body(payload)
    summary = f"{title} was {action}."
    if body:
        summary = f"{summary} {body}"
    return summarize_text(summary)


def github_content_title(payload: dict[str, Any]) -> str | None:
    for key in ("issue", "pull_request", "release"):
        value = payload.get(key)
        if isinstance(value, dict):
            title = clean_optional(value.get("title")) or clean_optional(value.get("name"))
            if title:
                return title
    comment = payload.get("comment") if isinstance(payload.get("comment"), dict) else {}
    return clean_optional(comment.get("body"))


def github_content_body(payload: dict[str, Any]) -> str | None:
    for key in ("comment", "issue", "pull_request", "release"):
        value = payload.get(key)
        if isinstance(value, dict):
            body = clean_optional(value.get("body"))
            if body:
                return body
    return None


def github_sender_login(payload: dict[str, Any]) -> str | None:
    sender = payload.get("sender") if isinstance(payload.get("sender"), dict) else {}
    return clean_optional(sender.get("login"))


def nested_text(payload: dict[str, Any], *keys: str) -> str | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return clean_optional(current)


def summarize_text(value: str, *, limit: int = 900) -> str:
    cleaned = WHITESPACE_PATTERN.sub(" ", value).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "."


def clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
