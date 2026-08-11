import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.extraction import build_source_event_extraction_handler
from app.db.models.connected_source import ConnectedSource, ConnectedSourceStatus
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.db.models.source_event import (
    AgentRun,
    AgentRunStatus,
    AgentRunType,
    SourceEvent,
    SourceEventStatus,
    SourcePayload,
    SourcePayloadRetentionPolicy,
)
from app.domains.source_events.schemas import (
    SourceEventIngestRequest,
    SourceEventIngestResponse,
    SourceEventProcessingResult,
    SourceEventResponse,
)

SourceEventHandler = Callable[[SourceEvent, SourcePayload | None], Awaitable[dict[str, Any]]]

DEFAULT_RULEBOOK_NAME = "developer_source_event_foundation"
DEFAULT_RULEBOOK_VERSION = "feature-15"


class SourceEventQueueService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def enqueue_event(self, payload: SourceEventIngestRequest) -> SourceEventIngestResponse:
        connected_source = await self._get_active_connected_source(payload.connected_source_id)
        event_timestamp = payload.source_event_timestamp or datetime.now(UTC)
        idempotency_key = payload.idempotency_key or build_idempotency_key(
            connected_source_id=payload.connected_source_id,
            external_event_id=payload.external_event_id,
            source_url=payload.source_url or connected_source.source_url,
            source_event_timestamp=event_timestamp,
            technical_metadata=payload.technical_metadata,
        )

        existing_event = await self._find_by_idempotency_key(idempotency_key)
        if existing_event is not None:
            return SourceEventIngestResponse(
                source_event=source_event_to_response(existing_event),
                is_duplicate=True,
            )

        now = datetime.now(UTC)
        source_event = SourceEvent(
            connected_source_id=connected_source.connected_source_id,
            partner_id=connected_source.partner_id,
            source_type=connected_source.source_type,
            external_event_id=clean_optional(payload.external_event_id),
            idempotency_key=idempotency_key,
            source_url=clean_optional(payload.source_url) or connected_source.source_url,
            source_event_timestamp=event_timestamp,
            technical_metadata=payload.technical_metadata,
            processing_status=SourceEventStatus.pending.value,
            attempt_count=0,
            max_attempts=payload.max_attempts,
            received_at=now,
        )
        self.db.add(source_event)
        await self.db.flush()

        source_payload = build_source_payload(
            source_event_id=source_event.source_event_id,
            source_type=connected_source.source_type,
            raw_payload_json=payload.raw_payload_json,
            raw_text_encrypted=payload.raw_text_encrypted,
            storage_object_id=payload.storage_object_id,
            retention_policy=payload.retention_policy,
            created_at=now,
        )
        if source_payload is not None:
            self.db.add(source_payload)

        await self.db.commit()
        return SourceEventIngestResponse(
            source_event=source_event_to_response(source_event),
            is_duplicate=False,
        )

    async def process_next_event(
        self,
        handler: SourceEventHandler | None = None,
    ) -> SourceEventProcessingResult:
        source_event = await self._claim_next_event()
        if source_event is None:
            return SourceEventProcessingResult(
                source_event=None,
                processed=False,
                status=None,
                message="No source events are ready for processing.",
            )
        return await self.process_event(source_event.source_event_id, handler=handler)

    async def process_event(
        self,
        source_event_id: uuid.UUID,
        handler: SourceEventHandler | None = None,
    ) -> SourceEventProcessingResult:
        source_event = await self._get_source_event_or_404(source_event_id)
        if source_event.processing_status not in {
            SourceEventStatus.pending.value,
            SourceEventStatus.processing.value,
            SourceEventStatus.retrying.value,
        }:
            return SourceEventProcessingResult(
                source_event=source_event_to_response(source_event),
                processed=False,
                status=SourceEventStatus(source_event.processing_status),
                message="Source event is already terminal.",
            )

        now = datetime.now(UTC)
        source_event.processing_status = SourceEventStatus.processing.value
        source_event.processing_started_at = now
        source_event.attempt_count += 1
        source_event.next_retry_at = None
        agent_run = AgentRun(
            run_type=AgentRunType.source_event_extraction.value,
            source_event_id=source_event.source_event_id,
            rulebook_name=DEFAULT_RULEBOOK_NAME,
            rulebook_version=DEFAULT_RULEBOOK_VERSION,
            status=AgentRunStatus.processing.value,
            input_fingerprint=source_event.idempotency_key,
            started_at=now,
        )
        self.db.add(agent_run)
        await self.db.flush()

        try:
            source_payload = await self._load_payload(source_event.source_event_id)
            output = await (
                handler or default_source_event_handler
            )(source_event, source_payload)
            await self._create_pending_update_from_agent_output(
                source_event=source_event,
                output=output,
            )
        except Exception as exc:
            return await self._mark_processing_failed(
                source_event=source_event,
                agent_run=agent_run,
                error_summary=str(exc)[:1200] or "Source event processing failed.",
            )

        finished_at = datetime.now(UTC)
        apply_agent_run_output_metadata(agent_run, output)
        agent_run.status = AgentRunStatus.succeeded.value
        agent_run.output_json = output
        agent_run.finished_at = finished_at
        source_event.processing_status = SourceEventStatus.succeeded.value
        source_event.last_error_summary = None
        source_event.processed_at = finished_at
        source_event.next_retry_at = None
        await self.db.commit()
        return SourceEventProcessingResult(
            source_event=source_event_to_response(source_event),
            processed=True,
            status=SourceEventStatus.succeeded,
            message="Source event processed.",
        )

    async def _claim_next_event(self) -> SourceEvent | None:
        now = datetime.now(UTC)
        statement = (
            select(SourceEvent)
            .where(
                SourceEvent.processing_status.in_(
                    [SourceEventStatus.pending.value, SourceEventStatus.retrying.value]
                )
            )
            .where(
                (SourceEvent.next_retry_at.is_(None)) | (SourceEvent.next_retry_at <= now)
            )
            .order_by(SourceEvent.received_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def _mark_processing_failed(
        self,
        *,
        source_event: SourceEvent,
        agent_run: AgentRun,
        error_summary: str,
    ) -> SourceEventProcessingResult:
        now = datetime.now(UTC)
        agent_run.status = AgentRunStatus.failed.value
        agent_run.error_summary = error_summary
        agent_run.finished_at = now
        source_event.last_error_summary = error_summary
        source_event.processed_at = None
        if source_event.attempt_count >= source_event.max_attempts:
            source_event.processing_status = SourceEventStatus.dead_letter.value
            source_event.next_retry_at = None
        else:
            source_event.processing_status = SourceEventStatus.retrying.value
            source_event.next_retry_at = now + timedelta(minutes=source_event.attempt_count)
        await self.db.commit()
        return SourceEventProcessingResult(
            source_event=source_event_to_response(source_event),
            processed=True,
            status=SourceEventStatus(source_event.processing_status),
            message=error_summary,
        )

    async def _get_active_connected_source(self, connected_source_id: uuid.UUID) -> ConnectedSource:
        result = await self.db.execute(
            select(ConnectedSource).where(
                ConnectedSource.connected_source_id == connected_source_id
            )
        )
        connected_source = result.scalar_one_or_none()
        if connected_source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connected source not found.",
            )
        if connected_source.status != ConnectedSourceStatus.active.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only active connected sources can enqueue source events.",
            )
        return connected_source

    async def _find_by_idempotency_key(self, idempotency_key: str) -> SourceEvent | None:
        result = await self.db.execute(
            select(SourceEvent).where(SourceEvent.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def _get_source_event_or_404(self, source_event_id: uuid.UUID) -> SourceEvent:
        result = await self.db.execute(
            select(SourceEvent).where(SourceEvent.source_event_id == source_event_id)
        )
        source_event = result.scalar_one_or_none()
        if source_event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source event not found.",
            )
        return source_event

    async def _load_payload(self, source_event_id: uuid.UUID) -> SourcePayload | None:
        result = await self.db.execute(
            select(SourcePayload).where(SourcePayload.source_event_id == source_event_id)
        )
        return result.scalar_one_or_none()

    async def _create_pending_update_from_agent_output(
        self,
        *,
        source_event: SourceEvent,
        output: dict[str, Any],
    ) -> None:
        command = output.get("pending_update_command")
        if not isinstance(command, dict):
            output["pending_updates_created"] = int(output.get("pending_updates_created") or 0)
            return

        source_event_key = require_command_text(command, "source_event_key")
        existing_update = await self._find_existing_update(source_event_key)
        if existing_update is not None:
            output["pending_updates_created"] = 0
            output["pending_update_duplicate"] = True
            output["existing_update_id"] = str(existing_update.update_id)
            return

        now = datetime.now(UTC)
        command_partner_id = uuid.UUID(require_command_text(command, "partner_id"))
        command_connected_source_id = uuid.UUID(
            require_command_text(command, "connected_source_id")
        )
        if command_partner_id != source_event.partner_id:
            raise ValueError("Agent pending update command partner_id does not match source event.")
        if command_connected_source_id != source_event.connected_source_id:
            raise ValueError(
                "Agent pending update command connected_source_id does not match source event."
            )

        update = PartnerUpdate(
            partner_id=command_partner_id,
            cycle_month=parse_command_date(command, "cycle_month"),
            title=require_command_text(command, "title"),
            summary=require_command_text(command, "summary"),
            source_type=require_command_text(command, "source_type"),
            source_label=clean_optional(command.get("source_label")),
            source_url=clean_optional(command.get("source_url")),
            source_event_key=source_event_key,
            connected_source_id=command_connected_source_id,
            source_event_id=source_event.source_event_id,
            status=PartnerUpdateStatus.pending.value,
            created_at=now,
            updated_at=now,
        )
        self.db.add(update)
        await self.db.flush()
        output["pending_updates_created"] = 1
        output["created_update_id"] = str(update.update_id)

    async def _find_existing_update(self, source_event_key: str) -> PartnerUpdate | None:
        result = await self.db.execute(
            select(PartnerUpdate).where(PartnerUpdate.source_event_key == source_event_key)
        )
        return result.scalar_one_or_none()


def build_source_payload(
    *,
    source_event_id: uuid.UUID,
    source_type: str,
    raw_payload_json: dict[str, Any] | None,
    raw_text_encrypted: str | None,
    storage_object_id: uuid.UUID | None,
    retention_policy: str | None,
    created_at: datetime,
) -> SourcePayload | None:
    if (
        retention_policy == SourcePayloadRetentionPolicy.technical_metadata_only.value
        or (source_type == "slack_channel" and retention_policy is None)
    ):
        return SourcePayload(
            source_event_id=source_event_id,
            raw_payload_json=None,
            raw_text_encrypted=None,
            storage_object_id=storage_object_id,
            retention_policy=SourcePayloadRetentionPolicy.technical_metadata_only.value,
            created_at=created_at,
        )
    if raw_payload_json is None and raw_text_encrypted is None and storage_object_id is None:
        return None
    return SourcePayload(
        source_event_id=source_event_id,
        raw_payload_json=raw_payload_json,
        raw_text_encrypted=raw_text_encrypted,
        storage_object_id=storage_object_id,
        retention_policy=(
            retention_policy
            or (
                SourcePayloadRetentionPolicy.encrypted_text.value
                if raw_text_encrypted
                else SourcePayloadRetentionPolicy.structured_payload.value
            )
        ),
        created_at=created_at,
    )


async def default_source_event_handler(
    source_event: SourceEvent,
    source_payload: SourcePayload | None,
) -> dict[str, Any]:
    return await build_source_event_extraction_handler()(source_event, source_payload)


def apply_agent_run_output_metadata(
    agent_run: AgentRun,
    output: dict[str, Any],
) -> None:
    rulebook_name = clean_optional(output.get("rulebook_name"))
    if rulebook_name is not None:
        agent_run.rulebook_name = rulebook_name

    rulebook_version = clean_optional(output.get("rulebook_version"))
    if rulebook_version is not None:
        agent_run.rulebook_version = rulebook_version

    model_name = clean_optional(output.get("model_name"))
    if model_name is not None:
        agent_run.model_name = model_name

    input_fingerprint = clean_optional(output.get("input_fingerprint"))
    if input_fingerprint is not None:
        agent_run.input_fingerprint = input_fingerprint


def build_idempotency_key(
    *,
    connected_source_id: uuid.UUID,
    external_event_id: str | None,
    source_url: str | None,
    source_event_timestamp: datetime,
    technical_metadata: dict[str, Any] | None,
) -> str:
    provider_identity = external_event_id or source_url or stable_json(technical_metadata or {})
    raw_key = (
        f"{connected_source_id}:"
        f"{provider_identity}:"
        f"{source_event_timestamp.astimezone(UTC).isoformat()}"
    )
    return hashlib.sha256(raw_key.encode()).hexdigest()


def stable_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def clean_optional(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def require_command_text(command: dict[str, Any], key: str) -> str:
    value = clean_optional(command.get(key))
    if value is None:
        raise ValueError(f"Agent pending update command is missing {key!r}.")
    return value


def parse_command_date(command: dict[str, Any], key: str) -> date:
    value = require_command_text(command, key)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Agent pending update command has invalid {key!r}.") from exc


def source_event_to_response(source_event: SourceEvent) -> SourceEventResponse:
    return SourceEventResponse(
        source_event_id=source_event.source_event_id,
        connected_source_id=source_event.connected_source_id,
        partner_id=source_event.partner_id,
        source_type=source_event.source_type,
        external_event_id=source_event.external_event_id,
        idempotency_key=source_event.idempotency_key,
        source_url=source_event.source_url,
        source_event_timestamp=source_event.source_event_timestamp,
        processing_status=SourceEventStatus(source_event.processing_status),
        attempt_count=source_event.attempt_count,
        max_attempts=source_event.max_attempts,
        last_error_summary=source_event.last_error_summary,
        received_at=source_event.received_at,
        processing_started_at=source_event.processing_started_at,
        processed_at=source_event.processed_at,
        next_retry_at=source_event.next_retry_at,
    )
