import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.db.models.partner_update import PartnerUpdateSourceType, PartnerUpdateStatus
from app.domains.contributor.updates.rich_text import (
    sanitize_update_summary_html,
    update_summary_text,
)


class PartnerUpdateCreatePayload(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=12000)
    source_type: PartnerUpdateSourceType = PartnerUpdateSourceType.manual
    source_label: str | None = Field(default=None, max_length=240)
    source_url: HttpUrl | None = None
    source_event_key: str | None = Field(default=None, max_length=320)

    @field_validator("title")
    @classmethod
    def required_text_must_be_clean(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be blank.")
        return cleaned

    @field_validator("summary")
    @classmethod
    def summary_must_be_safe_and_non_blank(cls, value: str) -> str:
        cleaned = sanitize_update_summary_html(value.strip())
        if not update_summary_text(cleaned).strip():
            raise ValueError("Value must not be blank.")
        return cleaned


class ManualUpdateCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=12000)

    @field_validator("title")
    @classmethod
    def required_text_must_be_clean(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be blank.")
        return cleaned

    @field_validator("summary")
    @classmethod
    def summary_must_be_safe_and_non_blank(cls, value: str) -> str:
        cleaned = sanitize_update_summary_html(value.strip())
        if not update_summary_text(cleaned).strip():
            raise ValueError("Value must not be blank.")
        return cleaned


class PartnerUpdateEditRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=12000)

    @field_validator("title")
    @classmethod
    def required_text_must_be_clean(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be blank.")
        return cleaned

    @field_validator("summary")
    @classmethod
    def summary_must_be_safe_and_non_blank(cls, value: str) -> str:
        cleaned = sanitize_update_summary_html(value.strip())
        if not update_summary_text(cleaned).strip():
            raise ValueError("Value must not be blank.")
        return cleaned


class PartnerUpdateResponse(BaseModel):
    update_id: uuid.UUID
    partner_id: uuid.UUID
    cycle: str
    title: str
    summary: str
    source_type: PartnerUpdateSourceType
    source_label: str | None
    source_url: str | None
    status: PartnerUpdateStatus
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    approved_by: uuid.UUID | None
    rejected_at: datetime | None
    rejected_by: uuid.UUID | None


class PartnerUpdateListResponse(BaseModel):
    updates: list[PartnerUpdateResponse]
