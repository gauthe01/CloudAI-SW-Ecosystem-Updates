import uuid
from datetime import datetime

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
    partner_id: uuid.UUID
    partner_name: str
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


class DraftEmailResponse(BaseModel):
    cycle: str
    partner_id: uuid.UUID | None
    partner_ids: list[uuid.UUID] = Field(default_factory=list)
    subject: str
    body: str
    update_count: int
