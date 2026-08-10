import uuid
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
    model_validator,
)

from app.db.models.partner_update import PartnerUpdateSourceType
from app.db.models.source_event import SourceEvent


class ExtractionDecision(StrEnum):
    ignore = "ignore"
    create_update = "create_update"


class ExtractionImportance(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class ExtractionOutputValidationError(ValueError):
    """Raised when model-like extraction output cannot be trusted."""


class DraftUpdateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=12000)
    source_label: str | None = Field(default=None, max_length=240)
    source_url: HttpUrl | None = None
    reasoning_category: str | None = Field(default=None, max_length=120)
    confidence: float = Field(ge=0, le=1)
    needs_human_attention: bool = False
    event_importance: ExtractionImportance = ExtractionImportance.medium
    dedupe_key_hint: str | None = Field(default=None, max_length=320)

    @field_validator("title", "summary")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be blank.")
        return cleaned

    @field_validator("source_label", "reasoning_category", "dedupe_key_hint")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        return cleaned


class SourceEventModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ExtractionDecision
    ignore_reason: str | None = Field(default=None, max_length=1200)
    draft_update: DraftUpdateOutput | None = None

    @field_validator("ignore_reason")
    @classmethod
    def clean_ignore_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def decision_must_match_payload(self) -> Self:
        if self.decision == ExtractionDecision.create_update and self.draft_update is None:
            raise ValueError("create_update decisions require draft_update.")
        if self.decision == ExtractionDecision.ignore and self.ignore_reason is None:
            raise ValueError("ignore decisions require ignore_reason.")
        if self.decision == ExtractionDecision.ignore and self.draft_update is not None:
            raise ValueError("ignore decisions must not include draft_update.")
        return self


@dataclass(frozen=True)
class PendingUpdateDraftCommand:
    partner_id: uuid.UUID
    cycle_month: date
    title: str
    summary: str
    source_type: PartnerUpdateSourceType
    source_label: str | None
    source_url: str | None
    source_event_key: str
    connected_source_id: uuid.UUID
    source_event_id: uuid.UUID
    reasoning_category: str | None
    confidence: float
    needs_human_attention: bool
    event_importance: ExtractionImportance
    dedupe_key_hint: str | None


def validate_source_event_model_output(raw_output: dict[str, Any]) -> SourceEventModelOutput:
    try:
        return SourceEventModelOutput.model_validate(raw_output)
    except ValidationError as exc:
        raise ExtractionOutputValidationError(str(exc)) from exc


def pending_update_command_from_model_output(
    *,
    source_event: SourceEvent,
    model_output: SourceEventModelOutput,
) -> PendingUpdateDraftCommand | None:
    if model_output.decision == ExtractionDecision.ignore:
        return None
    if model_output.draft_update is None:
        raise ExtractionOutputValidationError("create_update decisions require draft_update.")

    return PendingUpdateDraftCommand(
        partner_id=source_event.partner_id,
        cycle_month=source_event.source_event_timestamp.date().replace(day=1),
        title=model_output.draft_update.title,
        summary=model_output.draft_update.summary,
        source_type=partner_update_source_type_for_source_event(source_event.source_type),
        source_label=model_output.draft_update.source_label,
        source_url=(
            str(model_output.draft_update.source_url)
            if model_output.draft_update.source_url is not None
            else source_event.source_url
        ),
        source_event_key=source_event.idempotency_key,
        connected_source_id=source_event.connected_source_id,
        source_event_id=source_event.source_event_id,
        reasoning_category=model_output.draft_update.reasoning_category,
        confidence=model_output.draft_update.confidence,
        needs_human_attention=model_output.draft_update.needs_human_attention,
        event_importance=model_output.draft_update.event_importance,
        dedupe_key_hint=model_output.draft_update.dedupe_key_hint,
    )


def partner_update_source_type_for_source_event(source_type: str) -> PartnerUpdateSourceType:
    if source_type == "jira_issue":
        return PartnerUpdateSourceType.jira
    if source_type == "slack_channel":
        return PartnerUpdateSourceType.slack
    if source_type == "sharepoint_file":
        return PartnerUpdateSourceType.sharepoint
    if source_type == "confluence_page":
        return PartnerUpdateSourceType.confluence
    if source_type in {"github_repository", "github_issue", "github_pull_request"}:
        return PartnerUpdateSourceType.github
    raise ExtractionOutputValidationError(
        f"Cannot create pending update for unsupported source type {source_type!r}.",
    )
