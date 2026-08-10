"""connected sources

Revision ID: 0007_connected_sources
Revises: 0006_knowledge_uploads
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_connected_sources"
down_revision: str | None = "0006_knowledge_uploads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connected_sources",
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=300), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("external_identifier", sa.String(length=500), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.partner_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("connected_source_id"),
    )
    op.create_index(
        op.f("ix_connected_sources_partner_id"),
        "connected_sources",
        ["partner_id"],
    )
    op.create_index(
        op.f("ix_connected_sources_source_type"),
        "connected_sources",
        ["source_type"],
    )
    op.create_index(op.f("ix_connected_sources_status"), "connected_sources", ["status"])
    op.create_index(
        "ix_connected_sources_partner_status",
        "connected_sources",
        ["partner_id", "status"],
    )
    op.create_index(
        "ix_connected_sources_partner_type_external",
        "connected_sources",
        ["partner_id", "source_type", "external_identifier"],
    )

    op.create_table(
        "connected_source_jira_issues",
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_url", sa.Text(), nullable=False),
        sa.Column("issue_key", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(
            ["connected_source_id"],
            ["connected_sources.connected_source_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connected_source_id"),
    )
    op.create_table(
        "connected_source_slack_channels",
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_name", sa.String(length=240), nullable=False),
        sa.Column("channel_id", sa.String(length=120), nullable=False),
        sa.Column("bot_invited_confirmed", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connected_source_id"],
            ["connected_sources.connected_source_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connected_source_id"),
    )
    op.create_table(
        "connected_source_sharepoint_files",
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["connected_source_id"],
            ["connected_sources.connected_source_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connected_source_id"),
    )
    op.create_table(
        "connected_source_confluence_pages",
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("page_title", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["connected_source_id"],
            ["connected_sources.connected_source_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connected_source_id"),
    )
    op.create_table(
        "connected_source_github_targets",
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("target_kind", sa.String(length=64), nullable=False),
        sa.Column("repository", sa.String(length=300), nullable=True),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["connected_source_id"],
            ["connected_sources.connected_source_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connected_source_id"),
    )


def downgrade() -> None:
    op.drop_table("connected_source_github_targets")
    op.drop_table("connected_source_confluence_pages")
    op.drop_table("connected_source_sharepoint_files")
    op.drop_table("connected_source_slack_channels")
    op.drop_table("connected_source_jira_issues")
    op.drop_index("ix_connected_sources_partner_type_external", table_name="connected_sources")
    op.drop_index("ix_connected_sources_partner_status", table_name="connected_sources")
    op.drop_index(op.f("ix_connected_sources_status"), table_name="connected_sources")
    op.drop_index(op.f("ix_connected_sources_source_type"), table_name="connected_sources")
    op.drop_index(op.f("ix_connected_sources_partner_id"), table_name="connected_sources")
    op.drop_table("connected_sources")
