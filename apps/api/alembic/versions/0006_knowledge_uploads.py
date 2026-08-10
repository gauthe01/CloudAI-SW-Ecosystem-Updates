"""knowledge uploads

Revision ID: 0006_knowledge_uploads
Revises: 0005_update_lifecycle
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_knowledge_uploads"
down_revision: str | None = "0005_update_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_uploads",
        sa.Column("upload_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_backend", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("processing_status", sa.String(length=64), nullable=False),
        sa.Column("text_preview", sa.Text(), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.partner_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("upload_id"),
    )
    op.create_index(op.f("ix_knowledge_uploads_partner_id"), "knowledge_uploads", ["partner_id"])
    op.create_index(op.f("ix_knowledge_uploads_scope"), "knowledge_uploads", ["scope"])
    op.create_index(
        op.f("ix_knowledge_uploads_uploaded_by"),
        "knowledge_uploads",
        ["uploaded_by"],
    )
    op.create_index(
        "ix_knowledge_uploads_partner_scope_created",
        "knowledge_uploads",
        ["partner_id", "scope", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_uploads_partner_scope_created", table_name="knowledge_uploads")
    op.drop_index(op.f("ix_knowledge_uploads_uploaded_by"), table_name="knowledge_uploads")
    op.drop_index(op.f("ix_knowledge_uploads_scope"), table_name="knowledge_uploads")
    op.drop_index(op.f("ix_knowledge_uploads_partner_id"), table_name="knowledge_uploads")
    op.drop_table("knowledge_uploads")
