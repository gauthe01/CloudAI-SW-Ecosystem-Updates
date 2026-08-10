"""storage objects

Revision ID: 0010_storage_objects
Revises: 0009_source_event_queue
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010_storage_objects"
down_revision: str | None = "0009_source_event_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "storage_objects",
        sa.Column("storage_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("connected_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_backend", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("text_preview", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connected_source_id"],
            ["connected_sources.connected_source_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.partner_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("storage_object_id"),
    )
    op.create_index(
        op.f("ix_storage_objects_connected_source_id"),
        "storage_objects",
        ["connected_source_id"],
    )
    op.create_index(op.f("ix_storage_objects_partner_id"), "storage_objects", ["partner_id"])
    op.create_index(op.f("ix_storage_objects_source_kind"), "storage_objects", ["source_kind"])
    op.add_column(
        "source_payloads",
        sa.Column("storage_object_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_source_payloads_storage_object_id",
        "source_payloads",
        "storage_objects",
        ["storage_object_id"],
        ["storage_object_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_source_payloads_storage_object_id"),
        "source_payloads",
        ["storage_object_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_source_payloads_storage_object_id"), table_name="source_payloads")
    op.drop_constraint(
        "fk_source_payloads_storage_object_id",
        "source_payloads",
        type_="foreignkey",
    )
    op.drop_column("source_payloads", "storage_object_id")
    op.drop_index(op.f("ix_storage_objects_source_kind"), table_name="storage_objects")
    op.drop_index(op.f("ix_storage_objects_partner_id"), table_name="storage_objects")
    op.drop_index(op.f("ix_storage_objects_connected_source_id"), table_name="storage_objects")
    op.drop_table("storage_objects")
