"""knowledge upload candidates

Revision ID: 0015_knowledge_upload_candidates
Revises: 0014_due_date_text
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015_knowledge_upload_candidates"
down_revision: str | None = "0014_due_date_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_upload_candidates",
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("upload_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cycle_month", sa.Date(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_snippet", sa.Text(), nullable=True),
        sa.Column("section_label", sa.String(length=300), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parser_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partners.partner_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["knowledge_uploads.upload_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("candidate_id"),
    )
    op.create_index(
        op.f("ix_knowledge_upload_candidates_cycle_month"),
        "knowledge_upload_candidates",
        ["cycle_month"],
    )
    op.create_index(
        op.f("ix_knowledge_upload_candidates_partner_id"),
        "knowledge_upload_candidates",
        ["partner_id"],
    )
    op.create_index(
        op.f("ix_knowledge_upload_candidates_status"),
        "knowledge_upload_candidates",
        ["status"],
    )
    op.create_index(
        op.f("ix_knowledge_upload_candidates_upload_id"),
        "knowledge_upload_candidates",
        ["upload_id"],
    )
    op.create_index(
        "ix_knowledge_upload_candidates_upload_status",
        "knowledge_upload_candidates",
        ["upload_id", "status"],
    )
    op.create_index(
        "ix_knowledge_upload_candidates_partner_cycle",
        "knowledge_upload_candidates",
        ["partner_id", "cycle_month"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_upload_candidates_partner_cycle",
        table_name="knowledge_upload_candidates",
    )
    op.drop_index(
        "ix_knowledge_upload_candidates_upload_status",
        table_name="knowledge_upload_candidates",
    )
    op.drop_index(
        op.f("ix_knowledge_upload_candidates_upload_id"),
        table_name="knowledge_upload_candidates",
    )
    op.drop_index(
        op.f("ix_knowledge_upload_candidates_status"),
        table_name="knowledge_upload_candidates",
    )
    op.drop_index(
        op.f("ix_knowledge_upload_candidates_partner_id"),
        table_name="knowledge_upload_candidates",
    )
    op.drop_index(
        op.f("ix_knowledge_upload_candidates_cycle_month"),
        table_name="knowledge_upload_candidates",
    )
    op.drop_table("knowledge_upload_candidates")
