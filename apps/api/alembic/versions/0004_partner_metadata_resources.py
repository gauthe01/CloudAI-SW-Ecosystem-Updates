"""partner metadata and resources

Revision ID: 0004_partner_metadata_resources
Revises: 0003_partners_assignments
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_partner_metadata_resources"
down_revision: str | None = "0003_partners_assignments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "partner_metadata_snapshots",
        sa.Column("metadata_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_month", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("why_this_partner", sa.Text(), nullable=True),
        sa.Column("business_priority", sa.Text(), nullable=True),
        sa.Column("highlights_status", sa.Text(), nullable=True),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("execution_timeline", sa.Text(), nullable=True),
        sa.Column("saved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.partner_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["saved_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("metadata_id"),
        sa.UniqueConstraint("partner_id", "cycle_month", name="uq_partner_metadata_cycle"),
    )
    op.create_index(
        op.f("ix_partner_metadata_snapshots_cycle_month"),
        "partner_metadata_snapshots",
        ["cycle_month"],
        unique=False,
    )
    op.create_index(
        op.f("ix_partner_metadata_snapshots_partner_id"),
        "partner_metadata_snapshots",
        ["partner_id"],
        unique=False,
    )

    op.create_table(
        "partner_metadata_risks",
        sa.Column("risk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metadata_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("green_action", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("assigned_to", sa.String(length=240), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("ramification", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["metadata_id"],
            ["partner_metadata_snapshots.metadata_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("risk_id"),
    )
    op.create_index(
        op.f("ix_partner_metadata_risks_metadata_id"),
        "partner_metadata_risks",
        ["metadata_id"],
        unique=False,
    )

    op.create_table(
        "partner_resource_links",
        sa.Column("resource_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.partner_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("resource_link_id"),
    )
    op.create_index(
        op.f("ix_partner_resource_links_partner_id"),
        "partner_resource_links",
        ["partner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_partner_resource_links_partner_id"), table_name="partner_resource_links")
    op.drop_table("partner_resource_links")
    op.drop_index(
        op.f("ix_partner_metadata_risks_metadata_id"),
        table_name="partner_metadata_risks",
    )
    op.drop_table("partner_metadata_risks")
    op.drop_index(
        op.f("ix_partner_metadata_snapshots_partner_id"),
        table_name="partner_metadata_snapshots",
    )
    op.drop_index(
        op.f("ix_partner_metadata_snapshots_cycle_month"),
        table_name="partner_metadata_snapshots",
    )
    op.drop_table("partner_metadata_snapshots")
