import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models.source_event import SourceEventStatus


class SourceEventIngestRequest(BaseModel):
    connected_source_id: uuid.UUID
    external_event_id: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=128)
    source_url: str | None = Field(default=None, max_length=4000)
    source_event_timestamp: datetime | None = None
    technical_metadata: dict[str, Any] | None = None
    raw_payload_json: dict[str, Any] | None = None
    raw_text_encrypted: str | None = None
    storage_object_id: uuid.UUID | None = None
    retention_policy: str | None = Field(default=None, max_length=120)
    max_attempts: int = Field(default=3, ge=1, le=10)


class SourceEventResponse(BaseModel):
    source_event_id: uuid.UUID
    connected_source_id: uuid.UUID
    partner_id: uuid.UUID
    source_type: str
    external_event_id: str | None
    idempotency_key: str
    source_url: str | None
    source_event_timestamp: datetime
    processing_status: SourceEventStatus
    attempt_count: int
    max_attempts: int
    last_error_summary: str | None
    received_at: datetime
    processing_started_at: datetime | None
    processed_at: datetime | None
    next_retry_at: datetime | None


class SourceEventIngestResponse(BaseModel):
    source_event: SourceEventResponse
    is_duplicate: bool


class SourceEventProcessingResult(BaseModel):
    source_event: SourceEventResponse | None
    processed: bool
    status: SourceEventStatus | None
    message: str
