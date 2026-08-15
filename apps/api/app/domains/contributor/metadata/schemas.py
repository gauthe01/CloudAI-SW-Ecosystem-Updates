import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.db.models.partner_metadata import PartnerHealthStatus, ResourceLinkSourceKind


class PartnerMetadataRiskPayload(BaseModel):
    description: str = Field(default="", max_length=4000)
    green_action: str | None = Field(default=None, max_length=4000)
    severity: str | None = Field(default=None, max_length=64)
    assigned_to: str | None = Field(default=None, max_length=240)
    due_date: str | None = Field(default=None, max_length=240)
    ramification: str | None = Field(default=None, max_length=4000)

    @field_validator("description")
    @classmethod
    def description_must_be_clean(cls, value: str) -> str:
        return value.strip()

    @field_validator("due_date")
    @classmethod
    def due_date_must_be_clean(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else None
        return cleaned or None


class PartnerResourceLinkPayload(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: HttpUrl
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def title_must_be_clean(cls, value: str) -> str:
        return value.strip()


class PartnerMetadataSaveRequest(BaseModel):
    status: PartnerHealthStatus | None = None
    why_this_partner: str | None = Field(default=None, max_length=12000)
    business_priority: str = Field(min_length=1, max_length=12000)
    highlights_status: str = Field(min_length=1, max_length=12000)
    goals: str = Field(min_length=1, max_length=12000)
    execution_timeline: str | None = Field(default=None, max_length=12000)
    risks: list[PartnerMetadataRiskPayload] = Field(default_factory=list, max_length=50)
    resources: list[PartnerResourceLinkPayload] = Field(default_factory=list, max_length=100)

    @field_validator(
        "business_priority",
        "highlights_status",
        "goals",
    )
    @classmethod
    def required_metadata_field_must_be_clean(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This metadata field is required.")
        return cleaned


class PartnerMetadataRiskResponse(BaseModel):
    risk_id: uuid.UUID | None = None
    description: str
    green_action: str | None
    severity: str | None
    assigned_to: str | None
    due_date: str | None
    ramification: str | None


class PartnerResourceLinkResponse(BaseModel):
    resource_link_id: uuid.UUID
    title: str
    url: str
    description: str | None
    source_kind: ResourceLinkSourceKind
    disabled: bool
    archived_at: datetime | None


class PartnerMetadataResponse(BaseModel):
    metadata_id: uuid.UUID | None
    partner_id: uuid.UUID
    cycle: str
    status: PartnerHealthStatus | None
    why_this_partner: str | None
    business_priority: str | None
    highlights_status: str | None
    goals: str | None
    execution_timeline: str | None
    risks: list[PartnerMetadataRiskResponse]
    resources: list[PartnerResourceLinkResponse]
    saved_at: datetime | None
    saved_by: uuid.UUID | None
