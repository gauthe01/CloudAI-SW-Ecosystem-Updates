import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.partner import PartnerStatus


class AssignedContributorResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str


class AdminPartnerResponse(BaseModel):
    partner_id: uuid.UUID
    name: str
    description: str | None
    status: PartnerStatus
    assigned_contributors: list[AssignedContributorResponse]
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class AdminPartnerListResponse(BaseModel):
    partners: list[AdminPartnerResponse]


class AdminPartnerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=2000)
    assigned_contributor_user_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_must_be_clean(cls, value: str) -> str:
        return value.strip()


class AdminPartnerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=2000)
    assigned_contributor_user_ids: list[uuid.UUID] | None = None

    @field_validator("name")
    @classmethod
    def name_must_be_clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()
