import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.agents.rulebooks import Rulebook, RulebookLoader
from app.agents.runtime.client import build_ai_client_runtime
from app.core.config import Settings, get_settings
from app.db.models.source_event import SourceEvent, SourcePayload

from .model_adapter import OpenAISourceEventModelAdapter, SourceEventModelAdapter
from .output import (
    SourceEventModelOutput,
    pending_update_command_from_model_output,
    validate_source_event_model_output,
)
from .rulebooks import source_event_rulebook_name

SOURCE_EVENT_EXTRACTION_MODE_INFRASTRUCTURE_ONLY = "infrastructure_only"
SOURCE_EVENT_EXTRACTION_MODE_DRY_RUN = "dry_run"
RESULT_EXTRACTION_MODE_MODEL_DRY_RUN = "model_dry_run"
SUPPORTED_SOURCE_EVENT_EXTRACTION_MODES = {
    SOURCE_EVENT_EXTRACTION_MODE_INFRASTRUCTURE_ONLY,
    SOURCE_EVENT_EXTRACTION_MODE_DRY_RUN,
    RESULT_EXTRACTION_MODE_MODEL_DRY_RUN,
}


@dataclass(frozen=True)
class SourcePayloadReference:
    payload_available: bool
    retention_policy: str | None
    has_structured_payload: bool
    has_encrypted_text: bool
    storage_object_id: uuid.UUID | None


@dataclass(frozen=True)
class SourceEventExtractionInput:
    source_event_id: uuid.UUID
    connected_source_id: uuid.UUID
    partner_id: uuid.UUID
    source_type: str
    source_url: str | None
    external_event_id: str | None
    source_event_timestamp: datetime
    idempotency_key: str
    technical_metadata: dict[str, Any] | None
    payload: SourcePayloadReference
    input_fingerprint: str

    def to_model_payload(self) -> dict[str, Any]:
        return {
            "source_event_id": str(self.source_event_id),
            "connected_source_id": str(self.connected_source_id),
            "partner_id": str(self.partner_id),
            "source_type": self.source_type,
            "source_url": self.source_url,
            "external_event_id": self.external_event_id,
            "source_event_timestamp": self.source_event_timestamp.isoformat(),
            "idempotency_key": self.idempotency_key,
            "technical_metadata": self.technical_metadata or {},
            "payload": {
                "payload_available": self.payload.payload_available,
                "retention_policy": self.payload.retention_policy,
                "has_structured_payload": self.payload.has_structured_payload,
                "has_encrypted_text": self.payload.has_encrypted_text,
                "storage_object_id": (
                    str(self.payload.storage_object_id)
                    if self.payload.storage_object_id is not None
                    else None
                ),
            },
            "input_fingerprint": self.input_fingerprint,
        }


@dataclass(frozen=True)
class SourceEventExtractionResult:
    source_event_id: uuid.UUID
    pending_updates_created: int
    extraction_mode: str
    rulebook_name: str
    rulebook_version: str
    rulebook_status: str
    input_fingerprint: str
    model_name: str | None
    reason: str
    model_output_validated: bool = False
    model_decision: str | None = None
    ignore_reason: str | None = None
    draft_update_preview: dict[str, Any] | None = None

    def to_agent_output(self) -> dict[str, Any]:
        output = {
            "pending_updates_created": self.pending_updates_created,
            "source_event_id": str(self.source_event_id),
            "extraction_mode": self.extraction_mode,
            "rulebook_name": self.rulebook_name,
            "rulebook_version": self.rulebook_version,
            "rulebook_status": self.rulebook_status,
            "input_fingerprint": self.input_fingerprint,
            "model_name": self.model_name,
            "reason": self.reason,
        }
        if self.model_output_validated:
            output["model_output_validated"] = True
        if self.model_decision is not None:
            output["model_decision"] = self.model_decision
        if self.ignore_reason is not None:
            output["ignore_reason"] = self.ignore_reason
        if self.draft_update_preview is not None:
            output["draft_update_preview"] = self.draft_update_preview
        return output


class SourceEventExtractionOrchestrator:
    """Builds source-event agent inputs without deciding business meaning yet."""

    def __init__(
        self,
        *,
        rulebook_loader: RulebookLoader | None = None,
        settings: Settings | None = None,
        model_adapter: SourceEventModelAdapter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.rulebook_loader = rulebook_loader or RulebookLoader()
        self.model_adapter = model_adapter
        self.extraction_mode = normalize_source_event_extraction_mode(
            self.settings.ai_source_event_extraction_mode
        )

    async def extract(
        self,
        source_event: SourceEvent,
        source_payload: SourcePayload | None,
    ) -> SourceEventExtractionResult:
        rulebook_name = source_event_rulebook_name(source_event.source_type)
        rulebook = self.rulebook_loader.load(rulebook_name)
        extraction_input = build_source_event_extraction_input(source_event, source_payload)
        if self.extraction_mode in {
            SOURCE_EVENT_EXTRACTION_MODE_DRY_RUN,
            RESULT_EXTRACTION_MODE_MODEL_DRY_RUN,
        }:
            return await self._dry_run_extract(
                source_event=source_event,
                extraction_input=extraction_input,
                rulebook=rulebook,
            )
        return infrastructure_only_result(
            extraction_input=extraction_input,
            rulebook=rulebook,
        )

    async def _dry_run_extract(
        self,
        *,
        source_event: SourceEvent,
        extraction_input: SourceEventExtractionInput,
        rulebook: Rulebook,
    ) -> SourceEventExtractionResult:
        adapter = self.model_adapter or OpenAISourceEventModelAdapter(
            runtime=build_ai_client_runtime(self.settings),
            max_output_tokens=self.settings.ai_source_event_max_output_tokens,
        )
        model_output = validate_source_event_model_output(
            await adapter.extract(extraction_input=extraction_input, rulebook=rulebook)
        )
        command = pending_update_command_from_model_output(
            source_event=source_event,
            model_output=model_output,
        )
        return dry_run_result(
            extraction_input=extraction_input,
            rulebook=rulebook,
            model_name=adapter.model_name,
            model_output=model_output,
            draft_update_preview=(
                pending_update_command_preview(command) if command is not None else None
            ),
        )


def build_source_event_extraction_handler(
    orchestrator: SourceEventExtractionOrchestrator | None = None,
):
    runtime_orchestrator = orchestrator or SourceEventExtractionOrchestrator()

    async def handler(
        source_event: SourceEvent,
        source_payload: SourcePayload | None,
    ) -> dict[str, Any]:
        result = await runtime_orchestrator.extract(source_event, source_payload)
        return result.to_agent_output()

    return handler


def normalize_source_event_extraction_mode(mode: str | None) -> str:
    normalized = (mode or SOURCE_EVENT_EXTRACTION_MODE_INFRASTRUCTURE_ONLY).strip().lower()
    normalized = normalized.replace("-", "_")
    if normalized not in SUPPORTED_SOURCE_EVENT_EXTRACTION_MODES:
        raise ValueError(f"Unsupported AI_SOURCE_EVENT_EXTRACTION_MODE={mode!r}.")
    return normalized


def build_source_event_extraction_input(
    source_event: SourceEvent,
    source_payload: SourcePayload | None,
) -> SourceEventExtractionInput:
    payload_reference = SourcePayloadReference(
        payload_available=source_payload is not None,
        retention_policy=source_payload.retention_policy if source_payload else None,
        has_structured_payload=bool(source_payload and source_payload.raw_payload_json),
        has_encrypted_text=bool(source_payload and source_payload.raw_text_encrypted),
        storage_object_id=source_payload.storage_object_id if source_payload else None,
    )
    model_payload = {
        "source_event_id": str(source_event.source_event_id),
        "connected_source_id": str(source_event.connected_source_id),
        "partner_id": str(source_event.partner_id),
        "source_type": source_event.source_type,
        "source_url": source_event.source_url,
        "external_event_id": source_event.external_event_id,
        "source_event_timestamp": source_event.source_event_timestamp.isoformat(),
        "idempotency_key": source_event.idempotency_key,
        "technical_metadata": source_event.technical_metadata or {},
        "payload": {
            "payload_available": payload_reference.payload_available,
            "retention_policy": payload_reference.retention_policy,
            "has_structured_payload": payload_reference.has_structured_payload,
            "has_encrypted_text": payload_reference.has_encrypted_text,
            "storage_object_id": (
                str(payload_reference.storage_object_id)
                if payload_reference.storage_object_id is not None
                else None
            ),
        },
    }
    return SourceEventExtractionInput(
        source_event_id=source_event.source_event_id,
        connected_source_id=source_event.connected_source_id,
        partner_id=source_event.partner_id,
        source_type=source_event.source_type,
        source_url=source_event.source_url,
        external_event_id=source_event.external_event_id,
        source_event_timestamp=source_event.source_event_timestamp,
        idempotency_key=source_event.idempotency_key,
        technical_metadata=source_event.technical_metadata,
        payload=payload_reference,
        input_fingerprint=fingerprint_payload(model_payload),
    )


def dry_run_result(
    *,
    extraction_input: SourceEventExtractionInput,
    rulebook: Rulebook,
    model_name: str,
    model_output: SourceEventModelOutput,
    draft_update_preview: dict[str, Any] | None,
) -> SourceEventExtractionResult:
    if draft_update_preview is None:
        reason = (
            "Dry-run model output validated as ignore. No pending update was created."
        )
    else:
        reason = (
            "Dry-run model output validated as create_update. Pending update creation "
            "remains disabled until Feature 23B/23C finalize the production rulebook."
        )
    return SourceEventExtractionResult(
        source_event_id=extraction_input.source_event_id,
        pending_updates_created=0,
        extraction_mode=RESULT_EXTRACTION_MODE_MODEL_DRY_RUN,
        rulebook_name=rulebook.name,
        rulebook_version=rulebook.trace_version,
        rulebook_status=rulebook.status,
        input_fingerprint=extraction_input.input_fingerprint,
        model_name=model_name,
        reason=reason,
        model_output_validated=True,
        model_decision=model_output.decision.value,
        ignore_reason=model_output.ignore_reason,
        draft_update_preview=draft_update_preview,
    )


def infrastructure_only_result(
    *,
    extraction_input: SourceEventExtractionInput,
    rulebook: Rulebook,
) -> SourceEventExtractionResult:
    return SourceEventExtractionResult(
        source_event_id=extraction_input.source_event_id,
        pending_updates_created=0,
        extraction_mode="infrastructure_only",
        rulebook_name=rulebook.name,
        rulebook_version=rulebook.trace_version,
        rulebook_status=rulebook.status,
        input_fingerprint=extraction_input.input_fingerprint,
        model_name=None,
        reason=(
            "Agent extraction infrastructure is wired, but model-backed extraction "
            "is gated until Feature 23B/23C finalize the production rulebook."
        ),
    )


def pending_update_command_preview(command: Any) -> dict[str, Any]:
    return {
        "partner_id": str(command.partner_id),
        "cycle_month": command.cycle_month.isoformat(),
        "title": command.title,
        "summary": command.summary,
        "source_type": command.source_type.value,
        "source_label": command.source_label,
        "source_url": command.source_url,
        "source_event_key": command.source_event_key,
        "connected_source_id": str(command.connected_source_id),
        "source_event_id": str(command.source_event_id),
        "reasoning_category": command.reasoning_category,
        "confidence": command.confidence,
        "needs_human_attention": command.needs_human_attention,
        "event_importance": command.event_importance.value,
        "dedupe_key_hint": command.dedupe_key_hint,
    }


def fingerprint_payload(payload: dict[str, Any]) -> str:
    stable_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(stable_payload.encode("utf-8")).hexdigest()
