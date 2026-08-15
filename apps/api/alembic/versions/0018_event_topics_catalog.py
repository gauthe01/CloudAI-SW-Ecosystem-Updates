"""event topics catalog

Revision ID: 0018_event_topics_catalog
Revises: 0017_topic_updates
Create Date: 2026-08-15
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018_event_topics_catalog"
down_revision: str | None = "0017_topic_updates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_topics",
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("topic_id"),
        sa.UniqueConstraint("normalized_name"),
    )
    op.create_index(op.f("ix_event_topics_status"), "event_topics", ["status"])
    op.create_index("ix_event_topics_status_name", "event_topics", ["status", "name"])

    op.add_column(
        "topic_updates",
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_topic_updates_topic_id",
        "topic_updates",
        "event_topics",
        ["topic_id"],
        ["topic_id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_topic_updates_topic_id"), "topic_updates", ["topic_id"])
    op.create_index(
        "ix_topic_updates_topic_id_cycle_status",
        "topic_updates",
        ["topic_id", "cycle_month", "status"],
    )

    op.add_column(
        "knowledge_upload_candidates",
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_upload_candidates_topic_id",
        "knowledge_upload_candidates",
        "event_topics",
        ["topic_id"],
        ["topic_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_knowledge_upload_candidates_topic_id"),
        "knowledge_upload_candidates",
        ["topic_id"],
    )
    op.create_index(
        "ix_knowledge_upload_candidates_topic_cycle",
        "knowledge_upload_candidates",
        ["topic_id", "cycle_month"],
    )

    _backfill_event_topics()


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_upload_candidates_topic_cycle",
        table_name="knowledge_upload_candidates",
    )
    op.drop_index(
        op.f("ix_knowledge_upload_candidates_topic_id"),
        table_name="knowledge_upload_candidates",
    )
    op.drop_constraint(
        "fk_knowledge_upload_candidates_topic_id",
        "knowledge_upload_candidates",
        type_="foreignkey",
    )
    op.drop_column("knowledge_upload_candidates", "topic_id")

    op.drop_index("ix_topic_updates_topic_id_cycle_status", table_name="topic_updates")
    op.drop_index(op.f("ix_topic_updates_topic_id"), table_name="topic_updates")
    op.drop_constraint("fk_topic_updates_topic_id", "topic_updates", type_="foreignkey")
    op.drop_column("topic_updates", "topic_id")

    op.drop_index("ix_event_topics_status_name", table_name="event_topics")
    op.drop_index(op.f("ix_event_topics_status"), table_name="event_topics")
    op.drop_table("event_topics")


def _backfill_event_topics() -> None:
    connection = op.get_bind()
    labels = connection.execute(
        sa.text(
            """
            SELECT DISTINCT topic_label
            FROM topic_updates
            WHERE topic_label IS NOT NULL AND btrim(topic_label) <> ''
            """
        )
    ).scalars()
    now = datetime.now(UTC)
    normalized_to_topic: dict[str, uuid.UUID] = {}
    for label in labels:
        cleaned = " ".join(str(label).split())[:160]
        normalized = " ".join(cleaned.lower().split())[:180]
        if not cleaned or normalized in normalized_to_topic:
            continue
        topic_id = uuid.uuid4()
        normalized_to_topic[normalized] = topic_id
        connection.execute(
            sa.text(
                """
                INSERT INTO event_topics
                    (topic_id, name, normalized_name, status, created_at, updated_at)
                VALUES
                    (:topic_id, :name, :normalized_name, 'active', :created_at, :updated_at)
                ON CONFLICT (normalized_name) DO NOTHING
                """
            ),
            {
                "topic_id": topic_id,
                "name": cleaned,
                "normalized_name": normalized,
                "created_at": now,
                "updated_at": now,
            },
        )

    connection.execute(
        sa.text(
            """
            UPDATE topic_updates
            SET topic_id = event_topics.topic_id
            FROM event_topics
            WHERE lower(regexp_replace(btrim(topic_updates.topic_label), '\\s+', ' ', 'g'))
                = event_topics.normalized_name
            """
        )
    )
