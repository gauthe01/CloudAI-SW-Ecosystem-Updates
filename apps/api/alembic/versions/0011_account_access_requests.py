"""account access requests

Revision ID: 0011_account_access_requests
Revises: 0010_storage_objects
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_account_access_requests"
down_revision: str | None = "0010_storage_objects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_access_requests",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["created_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("request_id"),
    )
    op.create_index(
        op.f("ix_account_access_requests_email"),
        "account_access_requests",
        ["email"],
    )
    op.create_index(
        op.f("ix_account_access_requests_status"),
        "account_access_requests",
        ["status"],
    )
    op.create_index(
        "uq_account_access_requests_pending_email",
        "account_access_requests",
        ["email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_account_access_requests_pending_email", table_name="account_access_requests")
    op.drop_index(op.f("ix_account_access_requests_status"), table_name="account_access_requests")
    op.drop_index(op.f("ix_account_access_requests_email"), table_name="account_access_requests")
    op.drop_table("account_access_requests")
