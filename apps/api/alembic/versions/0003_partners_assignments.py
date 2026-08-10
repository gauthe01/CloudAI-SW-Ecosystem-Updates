"""partners and contributor assignments

Revision ID: 0003_partners_assignments
Revises: 0002_session_active_view
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_partners_assignments"
down_revision: str | None = "0002_session_active_view"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "partners",
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("partner_id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_partners_name"), "partners", ["name"], unique=False)
    op.create_index("ix_partners_name_lower", "partners", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "partner_contributor_assignments",
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.partner_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("partner_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("partner_contributor_assignments")
    op.drop_index("ix_partners_name_lower", table_name="partners")
    op.drop_index(op.f("ix_partners_name"), table_name="partners")
    op.drop_table("partners")
