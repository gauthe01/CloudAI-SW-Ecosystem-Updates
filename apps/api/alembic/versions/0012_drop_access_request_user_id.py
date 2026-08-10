"""drop access request user id

Revision ID: 0012_drop_access_request_user_id
Revises: 0011_account_access_requests
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012_drop_access_request_user_id"
down_revision: str | None = "0011_account_access_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE account_access_requests DROP COLUMN IF EXISTS requested_user_id")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE account_access_requests "
        "ADD COLUMN IF NOT EXISTS requested_user_id VARCHAR(120) NOT NULL DEFAULT ''"
    )
    op.execute("ALTER TABLE account_access_requests ALTER COLUMN requested_user_id DROP DEFAULT")
