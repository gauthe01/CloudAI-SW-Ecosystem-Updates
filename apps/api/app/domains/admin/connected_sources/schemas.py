import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.connected_source import ConnectedSourceStatus, ConnectedSourceType
from app.db.models.integration import IntegrationStatus, IntegrationType
from app.domains.contributor.connected_sources.schemas import ConnectedSourceDetailResponse


class AdminConnectedSourceUserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str


class AdminConnectedSourcePartnerResponse(BaseModel):
    partner_id: uuid.UUID
    name: str


class AdminConnectedSourceReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1200)


class AdminConnectedSourceResponse(BaseModel):
    connected_source_id: uuid.UUID
    partner: AdminConnectedSourcePartnerResponse
    source_type: ConnectedSourceType
    status: ConnectedSourceStatus
    review_bucket: str
    display_name: str
    source_url: str | None
    external_identifier: str | None
    details: ConnectedSourceDetailResponse
    requested_by: AdminConnectedSourceUserResponse
    approved_by: AdminConnectedSourceUserResponse | None
    required_integration_type: IntegrationType
    integration_status: IntegrationStatus | None
    integration_available: bool
    exact_duplicate_count: int
    access_test_summary: str | None
    approved_at: datetime | None
    rejected_at: datetime | None
    disabled_at: datetime | None
    archived_at: datetime | None
    last_tested_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminConnectedSourceListResponse(BaseModel):
    connected_sources: list[AdminConnectedSourceResponse]
