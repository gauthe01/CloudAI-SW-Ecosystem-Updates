"""topic updates

Revision ID: 0017_topic_updates
Revises: 0016_knowledge_upload_sessions
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017_topic_updates"
down_revision: str | None = "0016_knowledge_upload_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "topic_updates",
        sa.Column("topic_update_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_label", sa.String(length=160), nullable=False),
        sa.Column("cycle_month", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_label", sa.String(length=240), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_event_key", sa.String(length=320), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approved_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("topic_update_id"),
    )
    op.create_index(op.f("ix_topic_updates_cycle_month"), "topic_updates", ["cycle_month"])
    op.create_index(
        "ix_topic_updates_source_event_key",
        "topic_updates",
        ["source_event_key"],
        unique=True,
    )
    op.create_index(op.f("ix_topic_updates_status"), "topic_updates", ["status"])
    op.create_index(
        "ix_topic_updates_topic_cycle_status",
        "topic_updates",
        ["topic_label", "cycle_month", "status"],
    )
    op.create_index(op.f("ix_topic_updates_topic_label"), "topic_updates", ["topic_label"])

    op.add_column(
        "knowledge_upload_candidates",
        sa.Column("committed_topic_update_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_upload_candidates_committed_topic_update_id",
        "knowledge_upload_candidates",
        "topic_updates",
        ["committed_topic_update_id"],
        ["topic_update_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_knowledge_upload_candidates_committed_topic_update_id"),
        "knowledge_upload_candidates",
        ["committed_topic_update_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_knowledge_upload_candidates_committed_topic_update_id"),
        table_name="knowledge_upload_candidates",
    )
    op.drop_constraint(
        "fk_knowledge_upload_candidates_committed_topic_update_id",
        "knowledge_upload_candidates",
        type_="foreignkey",
    )
    op.drop_column("knowledge_upload_candidates", "committed_topic_update_id")

    op.drop_index(op.f("ix_topic_updates_topic_label"), table_name="topic_updates")
    op.drop_index("ix_topic_updates_topic_cycle_status", table_name="topic_updates")
    op.drop_index(op.f("ix_topic_updates_status"), table_name="topic_updates")
    op.drop_index("ix_topic_updates_source_event_key", table_name="topic_updates")
    op.drop_index(op.f("ix_topic_updates_cycle_month"), table_name="topic_updates")
    op.drop_table("topic_updates")
