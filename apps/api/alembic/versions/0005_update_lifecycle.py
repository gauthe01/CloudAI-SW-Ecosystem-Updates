"""update lifecycle

Revision ID: 0005_update_lifecycle
Revises: 0004_partner_metadata_resources
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_update_lifecycle"
down_revision: str | None = "0004_partner_metadata_resources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "partner_updates",
        sa.Column("update_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("rejected_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approved_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.partner_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("update_id"),
    )
    op.create_index(op.f("ix_partner_updates_cycle_month"), "partner_updates", ["cycle_month"])
    op.create_index(op.f("ix_partner_updates_partner_id"), "partner_updates", ["partner_id"])
    op.create_index(op.f("ix_partner_updates_status"), "partner_updates", ["status"])
    op.create_index(
        "ix_partner_updates_partner_cycle_status",
        "partner_updates",
        ["partner_id", "cycle_month", "status"],
    )
    op.create_index(
        "ix_partner_updates_source_event_key",
        "partner_updates",
        ["source_event_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_partner_updates_source_event_key", table_name="partner_updates")
    op.drop_index("ix_partner_updates_partner_cycle_status", table_name="partner_updates")
    op.drop_index(op.f("ix_partner_updates_status"), table_name="partner_updates")
    op.drop_index(op.f("ix_partner_updates_partner_id"), table_name="partner_updates")
    op.drop_index(op.f("ix_partner_updates_cycle_month"), table_name="partner_updates")
    op.drop_table("partner_updates")
