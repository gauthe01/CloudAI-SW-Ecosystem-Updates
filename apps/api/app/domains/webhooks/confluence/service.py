import hashlib
import html
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.connected_source import (
    ConnectedSource,
    ConnectedSourceConfluencePage,
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
from app.domains.webhooks.confluence.security import verify_confluence_signature

IGNORED_CONFLUENCE_EVENTS = {
    "page_deleted",
    "content_deleted",
    "attachment_created",
    "attachment_updated",
    "attachment_deleted",
}
MEANINGFUL_CONFLUENCE_KEYWORDS = {
    "blocked",
    "blocker",
    "decision",
    "delay",
    "issue",
    "milestone",
    "priority",
    "release",
    "risk",
    "status",
    "update",
}
WHITESPACE_PATTERN = re.compile(r"\s+")
TAG_PATTERN = re.compile(r"<[^>]+>")


class ConfluenceWebhookService:
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
        if not verify_confluence_signature(
            webhook_secret=webhook_secret,
            raw_body=raw_body,
            signature=signature,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Confluence signature.",
            )

        page_url = confluence_page_url(payload)
        if page_url is None:
            return {"status": "ignored", "reason": "Confluence payload did not include a page URL."}

        source_context = await self._load_active_confluence_source(page_url)
        if source_context is None:
            return {
                "status": "ignored",
                "reason": "No active Confluence connected source is mapped to this page.",
            }
        connected_source, confluence_page = source_context

        event_timestamp = confluence_event_timestamp(payload)
        event_id = confluence_event_id(payload, page_url)
        queued = await SourceEventQueueService(self.db).enqueue_event(
            SourceEventIngestRequest(
                connected_source_id=connected_source.connected_source_id,
                external_event_id=event_id,
                idempotency_key=f"confluence:{event_id}",
                source_url=confluence_page.page_url,
                source_event_timestamp=event_timestamp,
                technical_metadata=confluence_technical_metadata(payload, page_url),
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
            handler=ConfluenceSourceEventProcessor(
                db=self.db,
                payload=payload,
                confluence_page=confluence_page,
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
            select(Integration).where(
                Integration.integration_type == IntegrationType.confluence.value
            )
        )
        integration = result.scalar_one_or_none()
        if integration is None or integration.status != IntegrationStatus.enabled.value:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Confluence global integration is not enabled.",
            )

        webhook_secret = await get_integration_secret_value(
            self.db,
            self.settings,
            integration_type=IntegrationType.confluence,
            secret_name="webhook_secret",
        )
        if webhook_secret is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Confluence webhook secret is not configured.",
            )
        return webhook_secret

    async def _load_active_confluence_source(
        self,
        page_url: str,
    ) -> tuple[ConnectedSource, ConnectedSourceConfluencePage] | None:
        result = await self.db.execute(
            select(ConnectedSource, ConnectedSourceConfluencePage)
            .join(
                ConnectedSourceConfluencePage,
                ConnectedSourceConfluencePage.connected_source_id
                == ConnectedSource.connected_source_id,
            )
            .where(ConnectedSource.status == ConnectedSourceStatus.active.value)
        )
        normalized_page_url = normalize_match_url(page_url)
        for connected_source, confluence_page in result.all():
            if normalize_match_url(confluence_page.page_url) == normalized_page_url:
                return connected_source, confluence_page
        return None


class ConfluenceSourceEventProcessor:
    def __init__(
        self,
        *,
        db: AsyncSession,
        payload: dict[str, Any],
        confluence_page: ConnectedSourceConfluencePage,
    ) -> None:
        self.db = db
        self.payload = payload
        self.confluence_page = confluence_page

    async def process(
        self,
        source_event: SourceEvent,
        _payload: SourcePayload | None,
    ) -> dict[str, Any]:
        event_type = confluence_event_type(self.payload)
        if event_type in IGNORED_CONFLUENCE_EVENTS:
            return {
                "pending_updates_created": 0,
                "reason": "Confluence event type is ignored by the developer-owned rule.",
            }

        page_text = confluence_page_text(self.payload)
        if not is_meaningful_confluence_text(page_text):
            return {
                "pending_updates_created": 0,
                "reason": "Confluence page content did not meet the developer-owned rule.",
            }

        existing_update = await self._find_existing_update(source_event.idempotency_key)
        if existing_update is not None:
            return {
                "pending_updates_created": 0,
                "reason": "Pending update already exists for this Confluence event.",
                "update_id": str(existing_update.update_id),
            }

        page_title = (
            clean_optional(confluence_page_title(self.payload))
            or self.confluence_page.page_title
            or "Confluence page"
        )
        update = PartnerUpdate(
            partner_id=source_event.partner_id,
            cycle_month=source_event.source_event_timestamp.date().replace(day=1),
            title=confluence_update_title(page_title, event_type),
            summary=confluence_update_summary(page_title, page_text),
            source_type=PartnerUpdateSourceType.confluence.value,
            source_label=page_title[:240],
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


def confluence_event_type(payload: dict[str, Any]) -> str:
    return (
        clean_optional(payload.get("eventType"))
        or clean_optional(payload.get("event"))
        or clean_optional(payload.get("webhookEvent"))
        or "content_updated"
    ).lower()


def confluence_content(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("page", "content"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def confluence_page_url(payload: dict[str, Any]) -> str | None:
    content = confluence_content(payload)
    candidates = [
        clean_optional(payload.get("pageUrl")),
        clean_optional(payload.get("contentUrl")),
        clean_optional(payload.get("url")),
        clean_optional(content.get("url")),
        clean_optional(content.get("webUrl")),
    ]
    links = content.get("_links") if isinstance(content.get("_links"), dict) else {}
    if links:
        candidates.extend(
            [
                clean_optional(links.get("webui")),
            ]
        )

    for candidate in candidates:
        if candidate is None:
            continue
        if urlparse(candidate).scheme in {"http", "https"}:
            return candidate
        confluence_base = clean_optional(payload.get("baseUrl")) or clean_optional(
            links.get("base")
        )
        if confluence_base is None:
            continue
        joined = urljoin(confluence_base.rstrip("/") + "/", candidate)
        if urlparse(joined).scheme in {"http", "https"}:
            return joined
    return None


def confluence_page_title(payload: dict[str, Any]) -> str | None:
    content = confluence_content(payload)
    return clean_optional(content.get("title")) or clean_optional(payload.get("title"))


def confluence_page_text(payload: dict[str, Any]) -> str | None:
    content = confluence_content(payload)
    body = content.get("body") if isinstance(content.get("body"), dict) else {}
    storage = body.get("storage") if isinstance(body.get("storage"), dict) else {}
    candidates = [
        clean_optional(payload.get("bodyText")),
        clean_optional(payload.get("text")),
        clean_optional(payload.get("excerpt")),
        clean_optional(content.get("bodyText")),
        clean_optional(content.get("text")),
        clean_optional(content.get("excerpt")),
        clean_optional(storage.get("value")),
    ]
    for candidate in candidates:
        if candidate:
            return sanitize_confluence_text(candidate)
    return None


def confluence_event_timestamp(payload: dict[str, Any]) -> datetime:
    timestamp = payload.get("timestamp") or payload.get("createdDate") or payload.get("updatedDate")
    if isinstance(timestamp, int | float):
        value = timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
        return datetime.fromtimestamp(value, UTC)
    if isinstance(timestamp, str):
        normalized = timestamp.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).astimezone(UTC)
        except ValueError:
            return datetime.now(UTC)
    return datetime.now(UTC)


def confluence_event_id(payload: dict[str, Any], page_url: str) -> str:
    content = confluence_content(payload)
    event_type = confluence_event_type(payload)
    content_id = clean_optional(content.get("id")) or clean_optional(payload.get("pageId"))
    version = confluence_version_number(content) or clean_optional(payload.get("version"))
    timestamp = clean_optional(str(payload.get("timestamp"))) if payload.get("timestamp") else None
    components = [event_type, content_id or normalize_match_url(page_url), version, timestamp]
    if any(component for component in components[1:]):
        raw_event_id = ":".join(component or "none" for component in components)
        if len(raw_event_id) <= 100:
            return raw_event_id
        return hashlib.sha256(raw_event_id.encode()).hexdigest()
    return hashlib.sha256(stable_text_for_hash(payload).encode()).hexdigest()


def confluence_version_number(content: dict[str, Any]) -> str | None:
    version = content.get("version") if isinstance(content.get("version"), dict) else {}
    value = version.get("number") if version else None
    return clean_optional(str(value)) if value is not None else None


def confluence_technical_metadata(payload: dict[str, Any], page_url: str) -> dict[str, Any]:
    content = confluence_content(payload)
    return {
        "event_type": confluence_event_type(payload),
        "page_url_hash": hashlib.sha256(normalize_match_url(page_url).encode()).hexdigest(),
        "content_id": clean_optional(content.get("id")) or clean_optional(payload.get("pageId")),
        "version": confluence_version_number(content) or clean_optional(payload.get("version")),
        "space_key": confluence_space_key(content),
        "body_text_hash": (
            hashlib.sha256(confluence_page_text(payload).encode()).hexdigest()
            if confluence_page_text(payload)
            else None
        ),
    }


def confluence_space_key(content: dict[str, Any]) -> str | None:
    space = content.get("space") if isinstance(content.get("space"), dict) else {}
    return clean_optional(space.get("key")) if space else None


def is_meaningful_confluence_text(text: str | None) -> bool:
    if not text or len(text) < 20:
        return False
    lower_text = text.lower()
    return any(keyword in lower_text for keyword in MEANINGFUL_CONFLUENCE_KEYWORDS)


def confluence_update_title(page_title: str, event_type: str) -> str:
    label = event_type.replace("_", " ").strip().capitalize() or "Updated"
    return f"Confluence {label}: {page_title}"[:300]


def confluence_update_summary(page_title: str, page_text: str | None) -> str:
    summary = summarize_text(page_text or "")
    return f"{page_title}: {summary}"[:4000]


def summarize_text(text: str, *, limit: int = 700) -> str:
    cleaned = sanitize_confluence_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "."


def sanitize_confluence_text(value: str) -> str:
    without_tags = TAG_PATTERN.sub(" ", value)
    return WHITESPACE_PATTERN.sub(" ", html.unescape(without_tags)).strip()


def stable_text_for_hash(payload: dict[str, Any]) -> str:
    return str(sorted(payload.items()))


def normalize_match_url(value: str) -> str:
    parsed = urlparse(value.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{netloc}{path}{query}"


def clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
