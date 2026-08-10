import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceEventStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"
    retrying = "retrying"
    dead_letter = "dead_letter"


class SourcePayloadRetentionPolicy(StrEnum):
    technical_metadata_only = "technical_metadata_only"
    structured_payload = "structured_payload"
    encrypted_text = "encrypted_text"


class AgentRunStatus(StrEnum):
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class AgentRunType(StrEnum):
    source_event_extraction = "source_event_extraction"


class SourceEvent(Base):
    __tablename__ = "source_events"

    source_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    connected_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connected_sources.connected_source_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partners.partner_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_event_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    source_event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    technical_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=SourceEventStatus.pending.value,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SourcePayload(Base):
    __tablename__ = "source_payloads"

    source_payload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_events.source_event_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    raw_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    raw_text_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_object_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("storage_objects.storage_object_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    retention_policy: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_events.source_event_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    rulebook_name: Mapped[str] = mapped_column(String(240), nullable=False)
    rulebook_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    input_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
