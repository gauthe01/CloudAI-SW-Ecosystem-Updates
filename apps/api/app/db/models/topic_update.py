import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TopicUpdateStatus(StrEnum):
    approved = "approved"
    archived = "archived"


class EventTopicStatus(StrEnum):
    active = "active"
    archived = "archived"


class EventTopic(Base):
    __tablename__ = "event_topics"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EventTopicStatus.active.value,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
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


class TopicUpdate(Base):
    __tablename__ = "topic_updates"

    topic_update_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_topics.topic_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    topic_label: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    cycle_month: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="file")
    source_label: Mapped[str | None] = mapped_column(String(240), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_event_key: Mapped[str | None] = mapped_column(String(320), nullable=True)
    dedupe_fingerprint: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TopicUpdateStatus.approved.value,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
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
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index("ix_event_topics_status_name", "status", "name")
Index("ix_topic_updates_topic_cycle_status", "topic_label", "cycle_month", "status")
Index("ix_topic_updates_topic_id_cycle_status", "topic_id", "cycle_month", "status")
Index("ix_topic_updates_source_event_key", "source_event_key", unique=True)
Index(
    "ix_topic_updates_approved_dedupe_fingerprint",
    "dedupe_fingerprint",
    unique=True,
    postgresql_where=text("dedupe_fingerprint IS NOT NULL AND status = 'approved'"),
)
