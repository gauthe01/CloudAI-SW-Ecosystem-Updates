import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.db.models.partner_metadata import PartnerHealthStatus, ResourceLinkSourceKind
from app.db.models.partner_update import PartnerUpdateSourceType


class PresenterPartnerResponse(BaseModel):
    partner_id: uuid.UUID
    name: str
    description: str | None
    approved_updates_count: int
    last_activity_at: datetime | None


class PresenterPartnerListResponse(BaseModel):
    partners: list[PresenterPartnerResponse]


class PresenterUpdateResponse(BaseModel):
    update_id: uuid.UUID
    partner_id: uuid.UUID | None
    partner_name: str
    scope: str = "partner"
    topic_label: str | None = None
    cycle: str
    title: str
    summary: str
    source_type: PartnerUpdateSourceType
    source_label: str | None
    source_url: str | None
    approved_at: datetime | None
    approved_by: uuid.UUID | None


class PresenterUpdateListResponse(BaseModel):
    updates: list[PresenterUpdateResponse]


class PresenterMetadataRiskResponse(BaseModel):
    description: str
    green_action: str | None
    severity: str | None
    assigned_to: str | None
    due_date: str | None
    ramification: str | None


class PresenterResourceLinkResponse(BaseModel):
    resource_link_id: uuid.UUID
    title: str
    url: str
    description: str | None
    source_kind: ResourceLinkSourceKind
    disabled: bool


class PresenterMetadataResponse(BaseModel):
    partner_id: uuid.UUID
    partner_name: str
    cycle: str
    status: PartnerHealthStatus | None
    why_this_partner: str | None
    business_priority: str | None
    highlights_status: str | None
    goals: str | None
    execution_timeline: str | None
    risks: list[PresenterMetadataRiskResponse]
    resources: list[PresenterResourceLinkResponse]
    saved_at: datetime | None


class DecisionBoardItem(BaseModel):
    partner_id: uuid.UUID
    partner_name: str
    signal: str
    rationale: str
    severity: str


class PresenterAnalysisResponse(BaseModel):
    cycle: str
    partner_id: uuid.UUID | None
    partner_ids: list[uuid.UUID] = Field(default_factory=list)
    executive_summary: str
    decision_board: list[DecisionBoardItem]
    update_count: int
    partner_count: int
    source_mix: dict[str, int]


class DraftEmailRequest(BaseModel):
    cycle: str = Field(pattern=r"^\d{4}-\d{2}$")
    partner_id: uuid.UUID | None = None
    partner_ids: list[uuid.UUID] = Field(default_factory=list)
    date_start: date | None = None
    date_end: date | None = None


class DraftEmailResponse(BaseModel):
    cycle: str
    partner_id: uuid.UUID | None
    partner_ids: list[uuid.UUID] = Field(default_factory=list)
    subject: str
    body: str
    update_count: int


class PresenterAskRequest(BaseModel):
    cycle: str = Field(pattern=r"^\d{4}-\d{2}$")
    question: str = Field(min_length=1, max_length=1200)
    partner_id: uuid.UUID | None = None
    partner_ids: list[uuid.UUID] = Field(default_factory=list)
    date_start: date | None = None
    date_end: date | None = None


class PresenterAskSection(BaseModel):
    title: str
    body: str | None = None
    bullets: list[str] = Field(default_factory=list)


class PresenterAskTable(BaseModel):
    title: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class PresenterAskCitation(BaseModel):
    citation_id: str
    kind: str
    partner_name: str | None = None
    title: str | None = None
    summary: str | None = None
    cycle: str | None = None


class PresenterAskResponse(BaseModel):
    answer: str
    confidence: str = "medium"
    sections: list[PresenterAskSection] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    tables: list[PresenterAskTable] = Field(default_factory=list)
    citations: list[PresenterAskCitation] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    grounded: bool = True
    model: str | None = None


class PresenterVoiceTranscriptResponse(BaseModel):
    text: str


class PresenterVoiceSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class PresenterExecutiveSummaryRequest(BaseModel):
    cycle: str = Field(pattern=r"^\d{4}-\d{2}$")
    partner_id: uuid.UUID | None = None
    partner_ids: list[uuid.UUID] = Field(default_factory=list)
    date_start: date | None = None
    date_end: date | None = None


class PresenterExecutiveSummaryResponse(BaseModel):
    cycle: str
    partner_id: uuid.UUID | None = None
    partner_ids: list[uuid.UUID] = Field(default_factory=list)
    bullets: list[str]
    source_note: str | None = None
    update_count: int
    grounded: bool = True
    model: str | None = None


class PresenterDecisionBoardRequest(BaseModel):
    cycle: str = Field(pattern=r"^\d{4}-\d{2}$")
    partner_id: uuid.UUID | None = None
    partner_ids: list[uuid.UUID] = Field(default_factory=list)
    date_start: date | None = None
    date_end: date | None = None


class PresenterDecisionBoardSignal(BaseModel):
    partner_id: uuid.UUID | None = None
    partner_name: str | None = None
    priority: str | None = None
    title: str
    update_line: str
    action: str | None = None
    source_kind: str | None = None
    update_id: uuid.UUID | None = None
    metadata_risk_id: uuid.UUID | None = None


class PresenterDecisionBoardResponse(BaseModel):
    cycle: str
    partner_id: uuid.UUID | None = None
    partner_ids: list[uuid.UUID] = Field(default_factory=list)
    signals: list[PresenterDecisionBoardSignal]
    source_note: str | None = None
    update_count: int
    grounded: bool = True
    model: str | None = None
