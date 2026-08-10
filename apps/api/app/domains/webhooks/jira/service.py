import hashlib
import hmac
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.connected_source import (
    ConnectedSource,
    ConnectedSourceJiraIssue,
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
from app.domains.webhooks.jira.security import verify_jira_signature

JIRA_ISSUE_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
IGNORED_JIRA_EVENTS = {
    "jira:issue_deleted",
    "issue_deleted",
}
MEANINGFUL_CHANGED_FIELDS = {
    "assignee",
    "comment",
    "description",
    "duedate",
    "fixVersions",
    "issuelinks",
    "labels",
    "priority",
    "resolution",
    "status",
    "summary",
}


class JiraWebhookService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def handle_event_payload(
        self,
        *,
        raw_body: bytes,
        signature: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        webhook_secret = await self._get_enabled_webhook_secret()
        if not verify_jira_signature(
            webhook_secret=webhook_secret,
            raw_body=raw_body,
            signature=signature,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Jira signature.",
            )

        issue_key = extract_jira_issue_key(payload)
        if issue_key is None:
            return {"status": "ignored", "reason": "Jira payload did not include an issue key."}

        source_context = await self._load_active_jira_source(issue_key)
        if source_context is None:
            return {
                "status": "ignored",
                "reason": "No active Jira connected source is mapped to this issue.",
            }
        connected_source, jira_issue = source_context

        event_timestamp = jira_event_timestamp(payload)
        event_id = jira_event_id(payload, issue_key)
        assignee_account_id = account_id_from_user(issue_field(payload, "assignee"))
        reporter_account_id = account_id_from_user(issue_field(payload, "reporter"))
        queued = await SourceEventQueueService(self.db).enqueue_event(
            SourceEventIngestRequest(
                connected_source_id=connected_source.connected_source_id,
                external_event_id=event_id,
                idempotency_key=f"jira:{event_id}",
                source_url=jira_issue.issue_url,
                source_event_timestamp=event_timestamp,
                technical_metadata=jira_technical_metadata(
                    payload=payload,
                    issue_key=issue_key,
                    assignee_hash=self._hash_user(assignee_account_id),
                    reporter_hash=self._hash_user(reporter_account_id),
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
            handler=JiraSourceEventProcessor(
                db=self.db,
                payload=payload,
                jira_issue=jira_issue,
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
            select(Integration).where(Integration.integration_type == IntegrationType.jira.value)
        )
        integration = result.scalar_one_or_none()
        if integration is None or integration.status != IntegrationStatus.enabled.value:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Jira global integration is not enabled.",
            )

        webhook_secret = await get_integration_secret_value(
            self.db,
            self.settings,
            integration_type=IntegrationType.jira,
            secret_name="webhook_secret",
        )
        if webhook_secret is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Jira webhook secret is not configured.",
            )
        return webhook_secret

    async def _load_active_jira_source(
        self,
        issue_key: str,
    ) -> tuple[ConnectedSource, ConnectedSourceJiraIssue] | None:
        result = await self.db.execute(
            select(ConnectedSource, ConnectedSourceJiraIssue)
            .join(
                ConnectedSourceJiraIssue,
                ConnectedSourceJiraIssue.connected_source_id
                == ConnectedSource.connected_source_id,
            )
            .where(ConnectedSourceJiraIssue.issue_key == issue_key.upper())
            .where(ConnectedSource.status == ConnectedSourceStatus.active.value)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    def _hash_user(self, user_id: str | None) -> str | None:
        if user_id is None:
            return None
        return hmac.new(
            self.settings.app_secret_key.encode(),
            user_id.encode(),
            hashlib.sha256,
        ).hexdigest()


class JiraSourceEventProcessor:
    def __init__(
        self,
        *,
        db: AsyncSession,
        payload: dict[str, Any],
        jira_issue: ConnectedSourceJiraIssue,
    ) -> None:
        self.db = db
        self.payload = payload
        self.jira_issue = jira_issue

    async def process(
        self,
        source_event: SourceEvent,
        _payload: SourcePayload | None,
    ) -> dict[str, Any]:
        if not is_meaningful_jira_event(self.payload):
            return {
                "pending_updates_created": 0,
                "reason": "Jira event did not meet the developer-owned meaningfulness rule.",
            }

        existing_update = await self._find_existing_update(source_event.idempotency_key)
        if existing_update is not None:
            return {
                "pending_updates_created": 0,
                "reason": "Pending update already exists for this Jira event.",
                "update_id": str(existing_update.update_id),
            }

        issue_key = self.jira_issue.issue_key
        issue_summary = clean_optional(issue_field(self.payload, "summary")) or issue_key
        update = PartnerUpdate(
            partner_id=source_event.partner_id,
            cycle_month=source_event.source_event_timestamp.date().replace(day=1),
            title=jira_update_title(issue_key, issue_summary, self.payload),
            summary=jira_update_summary(issue_key, issue_summary, self.payload),
            source_type=PartnerUpdateSourceType.jira.value,
            source_label=issue_key,
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


def extract_jira_issue_key(payload: dict[str, Any]) -> str | None:
    issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
    key = clean_optional(issue.get("key")) or clean_optional(payload.get("issueKey"))
    if key is not None:
        return key.upper()

    url_candidates = [
        clean_optional(issue.get("self")),
        clean_optional(payload.get("issue_url")),
        clean_optional(payload.get("issueUrl")),
    ]
    for candidate in url_candidates:
        if candidate is None:
            continue
        match = JIRA_ISSUE_KEY_PATTERN.search(candidate.upper())
        if match:
            return match.group(1)
    return None


def jira_event_timestamp(payload: dict[str, Any]) -> datetime:
    timestamp = payload.get("timestamp")
    if isinstance(timestamp, int | float):
        value = timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
        return datetime.fromtimestamp(value, UTC)
    return datetime.now(UTC)


def jira_event_id(payload: dict[str, Any], issue_key: str) -> str:
    webhook_event = clean_optional(payload.get("webhookEvent")) or "jira:event"
    timestamp = clean_optional(str(payload.get("timestamp"))) if payload.get("timestamp") else None
    changelog_id = clean_optional(changelog(payload).get("id"))
    comment_id = clean_optional(comment(payload).get("id"))
    components = [webhook_event, issue_key, timestamp, changelog_id, comment_id]
    if any(component for component in components[2:]):
        return ":".join(component or "none" for component in components)
    return hashlib.sha256(str(payload).encode()).hexdigest()


def jira_technical_metadata(
    *,
    payload: dict[str, Any],
    issue_key: str,
    assignee_hash: str | None,
    reporter_hash: str | None,
) -> dict[str, Any]:
    return {
        "webhook_event": clean_optional(payload.get("webhookEvent")),
        "issue_key": issue_key,
        "issue_id": clean_optional(issue(payload).get("id")),
        "project_key": clean_optional(project(payload).get("key")),
        "issue_type": clean_optional(named_field(issue_field(payload, "issuetype"))),
        "status_name": clean_optional(named_field(issue_field(payload, "status"))),
        "priority_name": clean_optional(named_field(issue_field(payload, "priority"))),
        "changelog_id": clean_optional(changelog(payload).get("id")),
        "comment_id": clean_optional(comment(payload).get("id")),
        "changed_fields": changed_fields(payload),
        "assignee_hash": assignee_hash,
        "reporter_hash": reporter_hash,
    }


def is_meaningful_jira_event(payload: dict[str, Any]) -> bool:
    webhook_event = clean_optional(payload.get("webhookEvent"))
    if webhook_event in IGNORED_JIRA_EVENTS:
        return False
    if webhook_event in {"jira:issue_created", "issue_created", "comment_created"}:
        return True
    fields = set(changed_fields(payload))
    if not fields:
        return True
    return bool(fields & MEANINGFUL_CHANGED_FIELDS)


def jira_update_title(issue_key: str, issue_summary: str, payload: dict[str, Any]) -> str:
    event_label = jira_event_label(payload)
    trimmed_summary = issue_summary[:180].rstrip()
    if len(issue_summary) > 180:
        trimmed_summary = f"{trimmed_summary}..."
    return f"Jira {event_label} for {issue_key}: {trimmed_summary}"[:300]


def jira_update_summary(issue_key: str, issue_summary: str, payload: dict[str, Any]) -> str:
    fields = changed_fields(payload)
    status_name = clean_optional(named_field(issue_field(payload, "status")))
    priority_name = clean_optional(named_field(issue_field(payload, "priority")))
    parts = [
        f"{issue_key} received a Jira {jira_event_label(payload)}.",
        f"Issue summary: {issue_summary}.",
    ]
    if status_name:
        parts.append(f"Current status: {status_name}.")
    if priority_name:
        parts.append(f"Priority: {priority_name}.")
    if fields:
        parts.append(f"Changed fields: {', '.join(fields)}.")
    return " ".join(parts)


def jira_event_label(payload: dict[str, Any]) -> str:
    webhook_event = clean_optional(payload.get("webhookEvent")) or "event"
    return webhook_event.removeprefix("jira:").replace("_", " ")


def changed_fields(payload: dict[str, Any]) -> list[str]:
    items = changelog(payload).get("items")
    if not isinstance(items, list):
        return []
    fields: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        field = clean_optional(item.get("field"))
        if field is not None:
            fields.append(field)
    return fields


def issue(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("issue") if isinstance(payload.get("issue"), dict) else {}


def project(payload: dict[str, Any]) -> dict[str, Any]:
    fields = issue(payload).get("fields") if isinstance(issue(payload).get("fields"), dict) else {}
    project_value = fields.get("project")
    return project_value if isinstance(project_value, dict) else {}


def changelog(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("changelog") if isinstance(payload.get("changelog"), dict) else {}


def comment(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("comment") if isinstance(payload.get("comment"), dict) else {}


def issue_field(payload: dict[str, Any], field_name: str) -> Any:
    fields = issue(payload).get("fields") if isinstance(issue(payload).get("fields"), dict) else {}
    return fields.get(field_name)


def named_field(value: Any) -> str | None:
    if isinstance(value, dict):
        return clean_optional(value.get("name"))
    return clean_optional(value)


def account_id_from_user(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    return clean_optional(value.get("accountId")) or clean_optional(value.get("name"))


def clean_optional(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None
