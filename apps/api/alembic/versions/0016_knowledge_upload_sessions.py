"""knowledge upload sessions

Revision ID: 0016_knowledge_upload_sessions
Revises: 0015_knowledge_upload_candidates
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016_knowledge_upload_sessions"
down_revision: str | None = "0015_knowledge_upload_candidates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_upload_sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=240), nullable=True),
        sa.Column("inferred_cycle", sa.Date(), nullable=True),
        sa.Column("cycle_confidence", sa.String(length=32), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("partner_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("update_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unknown_name_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rulebook_name", sa.String(length=240), nullable=False),
        sa.Column("rulebook_version", sa.String(length=120), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.agent_run_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        op.f("ix_knowledge_upload_sessions_agent_run_id"),
        "knowledge_upload_sessions",
        ["agent_run_id"],
    )
    op.create_index(
        op.f("ix_knowledge_upload_sessions_inferred_cycle"),
        "knowledge_upload_sessions",
        ["inferred_cycle"],
    )
    op.create_index(
        op.f("ix_knowledge_upload_sessions_status"),
        "knowledge_upload_sessions",
        ["status"],
    )
    op.create_index(
        op.f("ix_knowledge_upload_sessions_uploaded_by"),
        "knowledge_upload_sessions",
        ["uploaded_by"],
    )

    op.add_column(
        "knowledge_uploads",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_uploads_session_id",
        "knowledge_uploads",
        "knowledge_upload_sessions",
        ["session_id"],
        ["session_id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_knowledge_uploads_session_id"), "knowledge_uploads", ["session_id"])

    op.add_column(
        "knowledge_upload_candidates",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "knowledge_upload_candidates",
        sa.Column("raw_label", sa.String(length=300), nullable=True),
    )
    op.add_column(
        "knowledge_upload_candidates",
        sa.Column("source_filename", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "knowledge_upload_candidates",
        sa.Column("source_location", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "knowledge_upload_candidates",
        sa.Column("committed_update_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_upload_candidates_session_id",
        "knowledge_upload_candidates",
        "knowledge_upload_sessions",
        ["session_id"],
        ["session_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_knowledge_upload_candidates_committed_update_id",
        "knowledge_upload_candidates",
        "partner_updates",
        ["committed_update_id"],
        ["update_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_knowledge_upload_candidates_committed_update_id"),
        "knowledge_upload_candidates",
        ["committed_update_id"],
    )
    op.create_index(
        op.f("ix_knowledge_upload_candidates_raw_label"),
        "knowledge_upload_candidates",
        ["raw_label"],
    )
    op.create_index(
        op.f("ix_knowledge_upload_candidates_session_id"),
        "knowledge_upload_candidates",
        ["session_id"],
    )

    op.create_table(
        "memory_chunks",
        sa.Column("memory_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("update_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_text", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("retrieval_enabled", sa.Boolean(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.partner_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["update_id"], ["partner_updates.update_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("memory_chunk_id"),
        sa.UniqueConstraint("update_id"),
    )
    op.create_index(op.f("ix_memory_chunks_partner_id"), "memory_chunks", ["partner_id"])
    op.create_index(op.f("ix_memory_chunks_update_id"), "memory_chunks", ["update_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_memory_chunks_update_id"), table_name="memory_chunks")
    op.drop_index(op.f("ix_memory_chunks_partner_id"), table_name="memory_chunks")
    op.drop_table("memory_chunks")

    op.drop_index(
        op.f("ix_knowledge_upload_candidates_session_id"),
        table_name="knowledge_upload_candidates",
    )
    op.drop_index(
        op.f("ix_knowledge_upload_candidates_raw_label"),
        table_name="knowledge_upload_candidates",
    )
    op.drop_index(
        op.f("ix_knowledge_upload_candidates_committed_update_id"),
        table_name="knowledge_upload_candidates",
    )
    op.drop_constraint(
        "fk_knowledge_upload_candidates_committed_update_id",
        "knowledge_upload_candidates",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_knowledge_upload_candidates_session_id",
        "knowledge_upload_candidates",
        type_="foreignkey",
    )
    op.drop_column("knowledge_upload_candidates", "committed_update_id")
    op.drop_column("knowledge_upload_candidates", "source_location")
    op.drop_column("knowledge_upload_candidates", "source_filename")
    op.drop_column("knowledge_upload_candidates", "raw_label")
    op.drop_column("knowledge_upload_candidates", "session_id")

    op.drop_index(op.f("ix_knowledge_uploads_session_id"), table_name="knowledge_uploads")
    op.drop_constraint("fk_knowledge_uploads_session_id", "knowledge_uploads", type_="foreignkey")
    op.drop_column("knowledge_uploads", "session_id")

    op.drop_index(
        op.f("ix_knowledge_upload_sessions_uploaded_by"),
        table_name="knowledge_upload_sessions",
    )
    op.drop_index(
        op.f("ix_knowledge_upload_sessions_status"),
        table_name="knowledge_upload_sessions",
    )
    op.drop_index(
        op.f("ix_knowledge_upload_sessions_inferred_cycle"),
        table_name="knowledge_upload_sessions",
    )
    op.drop_index(
        op.f("ix_knowledge_upload_sessions_agent_run_id"),
        table_name="knowledge_upload_sessions",
    )
    op.drop_table("knowledge_upload_sessions")
