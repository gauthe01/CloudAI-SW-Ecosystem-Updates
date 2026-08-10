"""session active view

Revision ID: 0002_session_active_view
Revises: 0001_identity_auth
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_session_active_view"
down_revision: str | None = "0001_identity_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_sessions",
        sa.Column(
            "active_view",
            sa.Enum("contributor", "presenter", "admin", name="role_type"),
            server_default="contributor",
            nullable=False,
        ),
    )
    op.alter_column("user_sessions", "active_view", server_default=None)


def downgrade() -> None:
    op.drop_column("user_sessions", "active_view")
