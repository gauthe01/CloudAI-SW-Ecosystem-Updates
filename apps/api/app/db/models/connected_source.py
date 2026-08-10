import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConnectedSourceType(StrEnum):
    jira_issue = "jira_issue"
    slack_channel = "slack_channel"
    sharepoint_file = "sharepoint_file"
    confluence_page = "confluence_page"
    github_repository = "github_repository"
    github_issue = "github_issue"
    github_pull_request = "github_pull_request"


class ConnectedSourceStatus(StrEnum):
    pending = "pending"
    needs_access_setup = "needs_access_setup"
    active = "active"
    rejected = "rejected"
    disabled = "disabled"
    archived = "archived"
    failed = "failed"


class ConnectedSource(Base):
    __tablename__ = "connected_sources"

    connected_source_id: Mapped[uuid.UUID] = mapped_column(
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
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=ConnectedSourceStatus.pending.value,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_identifier: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class ConnectedSourceJiraIssue(Base):
    __tablename__ = "connected_source_jira_issues"

    connected_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connected_sources.connected_source_id", ondelete="CASCADE"),
        primary_key=True,
    )
    issue_url: Mapped[str] = mapped_column(Text, nullable=False)
    issue_key: Mapped[str] = mapped_column(String(120), nullable=False)


class ConnectedSourceSlackChannel(Base):
    __tablename__ = "connected_source_slack_channels"

    connected_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connected_sources.connected_source_id", ondelete="CASCADE"),
        primary_key=True,
    )
    channel_name: Mapped[str] = mapped_column(String(240), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(120), nullable=False)
    bot_invited_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ConnectedSourceSharePointFile(Base):
    __tablename__ = "connected_source_sharepoint_files"

    connected_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connected_sources.connected_source_id", ondelete="CASCADE"),
        primary_key=True,
    )
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ConnectedSourceConfluencePage(Base):
    __tablename__ = "connected_source_confluence_pages"

    connected_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connected_sources.connected_source_id", ondelete="CASCADE"),
        primary_key=True,
    )
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    page_title: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ConnectedSourceGitHubTarget(Base):
    __tablename__ = "connected_source_github_targets"

    connected_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connected_sources.connected_source_id", ondelete="CASCADE"),
        primary_key=True,
    )
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    repository: Mapped[str | None] = mapped_column(String(300), nullable=True)
    number: Mapped[int | None] = mapped_column(Integer, nullable=True)


Index("ix_connected_sources_partner_status", "partner_id", "status")
Index(
    "ix_connected_sources_partner_type_external",
    "partner_id",
    "source_type",
    "external_identifier",
)
