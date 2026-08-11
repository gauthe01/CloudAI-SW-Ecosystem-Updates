import uuid
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import re
from html import escape
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

URL_PATTERN = re.compile(r"https?://[^\s<>)]+")
LEADING_BULLET_PATTERN = re.compile(r"^\s*(?:[-*]|\d+[.)]|•)\s+")
HTML_LIST_ITEM_PATTERN = re.compile(r"<li>(.*?)</li>", re.IGNORECASE | re.DOTALL)
SEMICOLON_CLAUSE_PATTERN = re.compile(r";\s+")
PLACEHOLDER_SOURCE_LABELS = {
    "jira link title",
    "link title",
    "source link title",
    "source title",
}
JIRA_KEY_LABEL_PATTERN = re.compile(r"^jira\s+[A-Z][A-Z0-9]+-\d+$", re.IGNORECASE)


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
    cycle_month: date | None = None
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

    @field_validator("cycle_month")
    @classmethod
    def require_month_start(cls, value: date | None) -> date | None:
        if value is not None and value.day != 1:
            raise ValueError("cycle_month must be the first day of the month.")
        return value

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
        cycle_month=(
            model_output.draft_update.cycle_month
            or source_event.source_event_timestamp.date().replace(day=1)
        ),
        title=model_output.draft_update.title,
        summary=format_model_update_summary(model_output.draft_update.summary),
        source_type=partner_update_source_type_for_source_event(source_event.source_type),
        source_label=normalize_source_label(
            model_output.draft_update.source_label,
            source_event=source_event,
        ),
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


def format_model_update_summary(summary: str) -> str:
    cleaned = summary.strip()
    if not cleaned:
        return cleaned
    if cleaned.lower().startswith(("<ul", "<ol")):
        return normalize_html_list_summary(cleaned)

    lines = [
        clause
        for line in cleaned.splitlines()
        if line.strip()
        for clause in split_semicolon_clauses(LEADING_BULLET_PATTERN.sub("", line.strip()))
    ]
    if not lines:
        return cleaned
    return "<ul>" + "".join(f"<li>{linkify_escaped_text(line)}</li>" for line in lines) + "</ul>"


def normalize_html_list_summary(summary: str) -> str:
    list_items = HTML_LIST_ITEM_PATTERN.findall(summary)
    if not list_items:
        return summary

    split_items = [
        clause
        for item in list_items
        for clause in split_semicolon_clauses(item.strip())
    ]
    if not split_items:
        return summary
    return "<ul>" + "".join(f"<li>{item}</li>" for item in split_items) + "</ul>"


def split_semicolon_clauses(value: str) -> list[str]:
    clauses = [clause.strip() for clause in SEMICOLON_CLAUSE_PATTERN.split(value) if clause.strip()]
    return clauses or [value]


def linkify_escaped_text(value: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in URL_PATTERN.finditer(value):
        url = match.group(0).rstrip(".,;")
        trailing = match.group(0)[len(url) :]
        parts.append(escape(value[cursor : match.start()]))
        escaped_url = escape(url, quote=True)
        parts.append(f'<a href="{escaped_url}">{escape(url)}</a>')
        parts.append(escape(trailing))
        cursor = match.end()
    parts.append(escape(value[cursor:]))
    return "".join(parts)


def normalize_source_label(label: str | None, *, source_event: SourceEvent) -> str | None:
    cleaned = label.strip() if label else None
    if cleaned and not is_generic_source_label(cleaned):
        return cleaned
    return source_label_from_metadata(source_event.technical_metadata or {})


def is_generic_source_label(label: str) -> bool:
    return label.lower() in PLACEHOLDER_SOURCE_LABELS or bool(
        JIRA_KEY_LABEL_PATTERN.fullmatch(label)
    )


def source_label_from_metadata(metadata: dict[str, Any]) -> str | None:
    issue_summary = metadata.get("issue_summary")
    if isinstance(issue_summary, str) and issue_summary.strip():
        return issue_summary.strip()

    source_items = metadata.get("source_items")
    if isinstance(source_items, list):
        for item in source_items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "issue_summary":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

    return None


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
