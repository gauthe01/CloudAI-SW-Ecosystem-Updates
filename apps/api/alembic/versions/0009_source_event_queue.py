"""source event queue

Revision ID: 0009_source_event_queue
Revises: 0008_global_integrations
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_source_event_queue"
down_revision: str | None = "0008_global_integrations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_events",
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("external_event_id", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("technical_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("processing_status", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["connected_source_id"],
            ["connected_sources.connected_source_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.partner_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_event_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        op.f("ix_source_events_connected_source_id"),
        "source_events",
        ["connected_source_id"],
    )
    op.create_index(op.f("ix_source_events_partner_id"), "source_events", ["partner_id"])
    op.create_index(op.f("ix_source_events_source_type"), "source_events", ["source_type"])
    op.create_index(
        op.f("ix_source_events_external_event_id"),
        "source_events",
        ["external_event_id"],
    )
    op.create_index(
        op.f("ix_source_events_source_url"),
        "source_events",
        ["source_url"],
    )
    op.create_index(
        op.f("ix_source_events_source_event_timestamp"),
        "source_events",
        ["source_event_timestamp"],
    )
    op.create_index(
        op.f("ix_source_events_processing_status"),
        "source_events",
        ["processing_status"],
    )
    op.create_index(
        "ix_source_events_queue_ready",
        "source_events",
        ["processing_status", "next_retry_at", "received_at"],
    )

    op.create_table(
        "source_payloads",
        sa.Column("source_payload_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_text_encrypted", sa.Text(), nullable=True),
        sa.Column("retention_policy", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["source_events.source_event_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_payload_id"),
        sa.UniqueConstraint("source_event_id"),
    )
    op.create_index(
        op.f("ix_source_payloads_source_event_id"),
        "source_payloads",
        ["source_event_id"],
    )

    op.create_table(
        "agent_runs",
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_type", sa.String(length=120), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_name", sa.String(length=160), nullable=True),
        sa.Column("rulebook_name", sa.String(length=240), nullable=False),
        sa.Column("rulebook_version", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["source_events.source_event_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("agent_run_id"),
    )
    op.create_index(op.f("ix_agent_runs_run_type"), "agent_runs", ["run_type"])
    op.create_index(op.f("ix_agent_runs_source_event_id"), "agent_runs", ["source_event_id"])
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"])

    op.add_column(
        "partner_updates",
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "partner_updates",
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_partner_updates_connected_source_id",
        "partner_updates",
        "connected_sources",
        ["connected_source_id"],
        ["connected_source_id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_partner_updates_source_event_id",
        "partner_updates",
        "source_events",
        ["source_event_id"],
        ["source_event_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_partner_updates_connected_source_id"),
        "partner_updates",
        ["connected_source_id"],
    )
    op.create_index(
        op.f("ix_partner_updates_source_event_id"),
        "partner_updates",
        ["source_event_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_partner_updates_source_event_id"), table_name="partner_updates")
    op.drop_index(op.f("ix_partner_updates_connected_source_id"), table_name="partner_updates")
    op.drop_constraint(
        "fk_partner_updates_source_event_id",
        "partner_updates",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_partner_updates_connected_source_id",
        "partner_updates",
        type_="foreignkey",
    )
    op.drop_column("partner_updates", "source_event_id")
    op.drop_column("partner_updates", "connected_source_id")
    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_source_event_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_run_type"), table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index(op.f("ix_source_payloads_source_event_id"), table_name="source_payloads")
    op.drop_table("source_payloads")
    op.drop_index("ix_source_events_queue_ready", table_name="source_events")
    op.drop_index(op.f("ix_source_events_processing_status"), table_name="source_events")
    op.drop_index(op.f("ix_source_events_source_event_timestamp"), table_name="source_events")
    op.drop_index(op.f("ix_source_events_source_url"), table_name="source_events")
    op.drop_index(op.f("ix_source_events_external_event_id"), table_name="source_events")
    op.drop_index(op.f("ix_source_events_source_type"), table_name="source_events")
    op.drop_index(op.f("ix_source_events_partner_id"), table_name="source_events")
    op.drop_index(op.f("ix_source_events_connected_source_id"), table_name="source_events")
    op.drop_table("source_events")
