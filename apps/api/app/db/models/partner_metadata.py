import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PartnerHealthStatus(StrEnum):
    green = "green"
    amber = "amber"
    red = "red"


class ResourceLinkSourceKind(StrEnum):
    manual = "manual"
    connected_source = "connected_source"


class PartnerMetadataSnapshot(Base):
    __tablename__ = "partner_metadata_snapshots"
    __table_args__ = (
        UniqueConstraint("partner_id", "cycle_month", name="uq_partner_metadata_cycle"),
    )

    metadata_id: Mapped[uuid.UUID] = mapped_column(
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
    cycle_month: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    why_this_partner: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_priority: Mapped[str | None] = mapped_column(Text, nullable=True)
    highlights_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_timeline: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
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

    risks: Mapped[list["PartnerMetadataRisk"]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class PartnerMetadataRisk(Base):
    __tablename__ = "partner_metadata_risks"

    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    metadata_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partner_metadata_snapshots.metadata_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    green_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(240), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    ramification: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshot: Mapped[PartnerMetadataSnapshot] = relationship(back_populates="risks")


class PartnerResourceLink(Base):
    __tablename__ = "partner_resource_links"

    resource_link_id: Mapped[uuid.UUID] = mapped_column(
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
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_kind: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=ResourceLinkSourceKind.manual.value,
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
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
