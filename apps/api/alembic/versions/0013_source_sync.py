"""source sync tracking

Revision ID: 0013_source_sync
Revises: 0012_drop_access_request_user_id
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_source_sync"
down_revision: str | None = "0012_drop_access_request_user_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_sync_states",
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cursor_value", sa.Text(), nullable=True),
        sa.Column("cursor_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connected_source_id"],
            ["connected_sources.connected_source_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connected_source_id"),
    )
    op.create_index(
        "ix_source_sync_states_next_sync_at",
        "source_sync_states",
        ["next_sync_at"],
    )

    op.create_table(
        "source_sync_runs",
        sa.Column("source_sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ignored_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["connected_source_id"],
            ["connected_sources.connected_source_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_sync_run_id"),
    )
    op.create_index(
        op.f("ix_source_sync_runs_connected_source_id"),
        "source_sync_runs",
        ["connected_source_id"],
    )
    op.create_index(op.f("ix_source_sync_runs_source_type"), "source_sync_runs", ["source_type"])
    op.create_index(op.f("ix_source_sync_runs_status"), "source_sync_runs", ["status"])
    op.create_index(op.f("ix_source_sync_runs_started_at"), "source_sync_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_source_sync_runs_started_at"), table_name="source_sync_runs")
    op.drop_index(op.f("ix_source_sync_runs_status"), table_name="source_sync_runs")
    op.drop_index(op.f("ix_source_sync_runs_source_type"), table_name="source_sync_runs")
    op.drop_index(
        op.f("ix_source_sync_runs_connected_source_id"),
        table_name="source_sync_runs",
    )
    op.drop_table("source_sync_runs")
    op.drop_index("ix_source_sync_states_next_sync_at", table_name="source_sync_states")
    op.drop_table("source_sync_states")
