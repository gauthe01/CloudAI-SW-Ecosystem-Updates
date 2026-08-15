"""partner metadata due date text

Revision ID: 0014_due_date_text
Revises: 0013_source_sync
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_due_date_text"
down_revision: str | None = "0013_source_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "partner_metadata_risks",
        "due_date",
        existing_type=sa.Date(),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="to_char(due_date, 'YYYY-MM')",
    )


def downgrade() -> None:
    op.alter_column(
        "partner_metadata_risks",
        "due_date",
        existing_type=sa.Text(),
        type_=sa.Date(),
        existing_nullable=True,
        postgresql_using=(
            "CASE "
            "WHEN due_date ~ '^\\d{4}-\\d{2}$' THEN (due_date || '-01')::date "
            "WHEN due_date ~ '^\\d{4}-\\d{2}-\\d{2}$' THEN due_date::date "
            "ELSE NULL "
            "END"
        ),
    )
