import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeUploadScope(StrEnum):
    admin_knowledge = "admin_knowledge"
    contributor_partner_file = "contributor_partner_file"


class KnowledgeUploadProcessingStatus(StrEnum):
    parsed = "parsed"
    stored = "stored"
    unsupported = "unsupported"


class KnowledgeUploadCandidateStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    dismissed = "dismissed"
    staged = "staged"
    committed = "committed"
    skipped = "skipped"


class KnowledgeUploadSessionStatus(StrEnum):
    analyzing = "analyzing"
    ready_for_review = "ready_for_review"
    committed = "committed"


class KnowledgeUploadCandidateReviewStatus(StrEnum):
    ready = "ready"
    needs_mapping = "needs_mapping"
    topic_pending = "topic_pending"
    likely_noise = "likely_noise"
    duplicate = "duplicate"


class KnowledgeUploadSession(Base):
    __tablename__ = "knowledge_upload_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=KnowledgeUploadSessionStatus.analyzing.value,
        index=True,
    )
    document_type: Mapped[str | None] = mapped_column(String(240), nullable=True)
    inferred_cycle: Mapped[date | None] = mapped_column(Date(), nullable=True, index=True)
    cycle_confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    partner_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    update_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown_name_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_json: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    rulebook_name: Mapped[str] = mapped_column(String(240), nullable=False)
    rulebook_version: Mapped[str] = mapped_column(String(120), nullable=False)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.agent_run_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class KnowledgeUpload(Base):
    __tablename__ = "knowledge_uploads"

    upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_upload_sessions.session_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partners.partner_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(64), nullable=False)
    text_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


Index(
    "ix_knowledge_uploads_partner_scope_created",
    "partner_id",
    "scope",
    "created_at",
)


class KnowledgeUploadCandidate(Base):
    __tablename__ = "knowledge_upload_candidates"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_upload_sessions.session_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_uploads.upload_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partners.partner_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cycle_month: Mapped[date | None] = mapped_column(Date(), nullable=True, index=True)
    raw_label: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    review_status: Mapped[str] = mapped_column(String(64), nullable=False, default="ready")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=KnowledgeUploadCandidateStatus.pending.value,
        index=True,
    )
    parser_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    committed_update_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partner_updates.update_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    committed_topic_update_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topic_updates.topic_update_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


Index(
    "ix_knowledge_upload_candidates_upload_status",
    "upload_id",
    "status",
)
Index(
    "ix_knowledge_upload_candidates_partner_cycle",
    "partner_id",
    "cycle_month",
)


class MemoryChunk(Base):
    __tablename__ = "memory_chunks"

    memory_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partners.partner_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    update_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partner_updates.update_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    memory_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="knowledge_upload")
    retrieval_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
