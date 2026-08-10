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
    ConnectedSourceSlackChannel,
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
from app.domains.webhooks.slack.security import verify_slack_signature

SLACK_EVENT_CALLBACK = "event_callback"
SLACK_URL_VERIFICATION = "url_verification"
SLACK_MESSAGE_EVENT = "message"
IGNORED_MESSAGE_SUBTYPES = {
    "channel_join",
    "channel_leave",
    "message_deleted",
}
MEANINGFUL_KEYWORDS = {
    "action",
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


class SlackWebhookService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def handle_event_payload(
        self,
        *,
        raw_body: bytes,
        timestamp: str | None,
        signature: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        signing_secret = await self._get_enabled_signing_secret()
        if not verify_slack_signature(
            signing_secret=signing_secret,
            raw_body=raw_body,
            timestamp=timestamp,
            signature=signature,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Slack signature.",
            )

        payload_type = payload.get("type")
        if payload_type == SLACK_URL_VERIFICATION:
            return {"challenge": payload.get("challenge")}
        if payload_type != SLACK_EVENT_CALLBACK:
            return {"status": "ignored", "reason": "Unsupported Slack payload type."}

        event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        if not should_process_slack_event(event):
            return {"status": "ignored", "reason": "Slack event is not a supported message."}

        channel_id = clean_optional(event.get("channel"))
        if channel_id is None:
            return {"status": "ignored", "reason": "Slack event did not include a channel."}

        source_context = await self._load_active_slack_source(channel_id)
        if source_context is None:
            return {
                "status": "ignored",
                "reason": "No active Slack connected source is mapped to this channel.",
            }
        connected_source, slack_channel = source_context

        event_timestamp = slack_event_timestamp(payload, event)
        source_url = slack_channel_url(slack_channel.channel_id)
        technical_metadata = slack_technical_metadata(
            payload=payload,
            event=event,
            channel_name=slack_channel.channel_name,
            user_hash=self._hash_user(clean_optional(event.get("user"))),
        )
        event_id = clean_optional(payload.get("event_id")) or slack_fallback_event_id(event)

        queued = await SourceEventQueueService(self.db).enqueue_event(
            SourceEventIngestRequest(
                connected_source_id=connected_source.connected_source_id,
                external_event_id=event_id,
                idempotency_key=f"slack:{event_id}",
                source_url=source_url,
                source_event_timestamp=event_timestamp,
                technical_metadata=technical_metadata,
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
            handler=SlackSourceEventProcessor(
                db=self.db,
                slack_event=event,
                slack_channel=slack_channel,
            ).process,
        )
        return {
            "status": "processed",
            "source_event_id": str(queued.source_event.source_event_id),
            "processing_status": processing.status.value if processing.status is not None else None,
            "message": processing.message,
        }

    async def _get_enabled_signing_secret(self) -> str:
        result = await self.db.execute(
            select(Integration).where(Integration.integration_type == IntegrationType.slack.value)
        )
        integration = result.scalar_one_or_none()
        if integration is None or integration.status != IntegrationStatus.enabled.value:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Slack global integration is not enabled.",
            )

        signing_secret = await get_integration_secret_value(
            self.db,
            self.settings,
            integration_type=IntegrationType.slack,
            secret_name="signing_secret",
        )
        if signing_secret is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Slack signing secret is not configured.",
            )
        return signing_secret

    async def _load_active_slack_source(
        self,
        channel_id: str,
    ) -> tuple[ConnectedSource, ConnectedSourceSlackChannel] | None:
        result = await self.db.execute(
            select(ConnectedSource, ConnectedSourceSlackChannel)
            .join(
                ConnectedSourceSlackChannel,
                ConnectedSourceSlackChannel.connected_source_id
                == ConnectedSource.connected_source_id,
            )
            .where(ConnectedSourceSlackChannel.channel_id == channel_id)
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


class SlackSourceEventProcessor:
    def __init__(
        self,
        *,
        db: AsyncSession,
        slack_event: dict[str, Any],
        slack_channel: ConnectedSourceSlackChannel,
    ) -> None:
        self.db = db
        self.slack_event = slack_event
        self.slack_channel = slack_channel

    async def process(
        self,
        source_event: SourceEvent,
        _payload: SourcePayload | None,
    ) -> dict[str, Any]:
        text = clean_slack_text(clean_optional(self.slack_event.get("text")) or "")
        if not is_meaningful_slack_text(text):
            return {
                "pending_updates_created": 0,
                "reason": "Slack message did not meet the developer-owned meaningfulness rule.",
            }

        existing_update = await self._find_existing_update(source_event.idempotency_key)
        if existing_update is not None:
            return {
                "pending_updates_created": 0,
                "reason": "Pending update already exists for this Slack event.",
                "update_id": str(existing_update.update_id),
            }

        update = PartnerUpdate(
            partner_id=source_event.partner_id,
            cycle_month=source_event.source_event_timestamp.date().replace(day=1),
            title=slack_update_title(text, self.slack_channel.channel_name),
            summary=slack_update_summary(text, self.slack_channel.channel_name),
            source_type=PartnerUpdateSourceType.slack.value,
            source_label=self.slack_channel.channel_name,
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


def should_process_slack_event(event: dict[str, Any]) -> bool:
    if event.get("type") != SLACK_MESSAGE_EVENT:
        return False
    subtype = clean_optional(event.get("subtype"))
    return subtype not in IGNORED_MESSAGE_SUBTYPES


def slack_event_timestamp(payload: dict[str, Any], event: dict[str, Any]) -> datetime:
    ts = clean_optional(event.get("ts")) or clean_optional(event.get("event_ts"))
    if ts is not None:
        try:
            return datetime.fromtimestamp(float(ts), UTC)
        except ValueError:
            pass
    event_time = payload.get("event_time")
    if isinstance(event_time, (int, float)):
        return datetime.fromtimestamp(event_time, UTC)
    return datetime.now(UTC)


def slack_technical_metadata(
    *,
    payload: dict[str, Any],
    event: dict[str, Any],
    channel_name: str,
    user_hash: str | None,
) -> dict[str, Any]:
    return {
        "slack_event_id": clean_optional(payload.get("event_id")),
        "channel_id": clean_optional(event.get("channel")),
        "channel_name": channel_name,
        "message_ts": clean_optional(event.get("ts")),
        "thread_ts": clean_optional(event.get("thread_ts")),
        "is_thread_reply": bool(
            event.get("thread_ts") and event.get("thread_ts") != event.get("ts")
        ),
        "sender_hash": user_hash,
        "message_subtype": clean_optional(event.get("subtype")),
    }


def slack_fallback_event_id(event: dict[str, Any]) -> str:
    raw = ":".join(
        [
            clean_optional(event.get("channel")) or "unknown-channel",
            clean_optional(event.get("ts")) or "unknown-ts",
            clean_optional(event.get("thread_ts")) or "no-thread",
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def slack_channel_url(channel_id: str) -> str:
    return f"https://slack.com/app_redirect?channel={channel_id}"


def clean_slack_text(text: str) -> str:
    without_mentions = re.sub(r"<@([A-Z0-9]+)>", "someone", text)
    without_links = re.sub(r"<([^|>]+)\\|([^>]+)>", r"\\2", without_mentions)
    without_angle_links = re.sub(r"<([^>]+)>", r"\\1", without_links)
    return re.sub(r"\\s+", " ", without_angle_links).strip()


def is_meaningful_slack_text(text: str) -> bool:
    if len(text) >= 20:
        return True
    lowered = text.lower()
    return any(keyword in lowered for keyword in MEANINGFUL_KEYWORDS)


def slack_update_title(text: str, channel_name: str) -> str:
    trimmed = text[:84].rstrip()
    if len(text) > 84:
        trimmed = f"{trimmed}..."
    return f"Slack update from {channel_name}: {trimmed}"[:300]


def slack_update_summary(text: str, channel_name: str) -> str:
    return (
        f"Slack discussion in {channel_name} surfaced a potential partner update: {text}"
    )


def clean_optional(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None
