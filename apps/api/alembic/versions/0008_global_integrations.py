"""global integrations

Revision ID: 0008_global_integrations
Revises: 0007_connected_sources
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_global_integrations"
down_revision: str | None = "0007_connected_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("integration_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(length=64), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("integration_id"),
        sa.UniqueConstraint("integration_type"),
    )
    op.create_index(op.f("ix_integrations_status"), "integrations", ["status"])

    op.create_table(
        "integration_secrets",
        sa.Column("integration_secret_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("secret_name", sa.String(length=120), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("value_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["integration_id"],
            ["integrations.integration_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("integration_secret_id"),
        sa.UniqueConstraint("integration_id", "secret_name"),
    )
    op.create_index(
        op.f("ix_integration_secrets_integration_id"),
        "integration_secrets",
        ["integration_id"],
    )

    op.create_table(
        "integration_test_runs",
        sa.Column("test_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("run_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["integration_id"],
            ["integrations.integration_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["run_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("test_run_id"),
    )
    op.create_index(
        op.f("ix_integration_test_runs_integration_id"),
        "integration_test_runs",
        ["integration_id"],
    )
    op.create_index(
        op.f("ix_integration_test_runs_status"),
        "integration_test_runs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_test_runs_status"), table_name="integration_test_runs")
    op.drop_index(
        op.f("ix_integration_test_runs_integration_id"),
        table_name="integration_test_runs",
    )
    op.drop_table("integration_test_runs")
    op.drop_index(op.f("ix_integration_secrets_integration_id"), table_name="integration_secrets")
    op.drop_table("integration_secrets")
    op.drop_index(op.f("ix_integrations_status"), table_name="integrations")
    op.drop_table("integrations")
