from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.integration import IntegrationStatus, IntegrationTestStatus, IntegrationType


class IntegrationFieldResponse(BaseModel):
    name: str
    label: str
    input_type: str
    required: bool
    configured: bool
    last_updated_at: datetime | None


class IntegrationTestRunResponse(BaseModel):
    test_run_id: str
    status: IntegrationTestStatus
    started_at: datetime
    finished_at: datetime | None
    result_summary: str | None


class IntegrationResponse(BaseModel):
    integration_id: str
    integration_type: IntegrationType
    display_name: str
    description: str
    status: IntegrationStatus
    required_configured_count: int
    required_field_count: int
    webhook_url: str | None
    fields: list[IntegrationFieldResponse]
    last_tested_at: datetime | None
    last_test_status: IntegrationTestStatus | None
    last_error_summary: str | None
    enabled_at: datetime | None
    disabled_at: datetime | None
    recent_test_runs: list[IntegrationTestRunResponse]
    created_at: datetime
    updated_at: datetime


class IntegrationListResponse(BaseModel):
    integrations: list[IntegrationResponse]


class IntegrationCredentialUpdateRequest(BaseModel):
    secrets: dict[str, str] = Field(default_factory=dict)


class IntegrationActionResponse(BaseModel):
    integration: IntegrationResponse
