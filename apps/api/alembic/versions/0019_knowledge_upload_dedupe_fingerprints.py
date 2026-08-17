"""knowledge upload dedupe fingerprints

Revision ID: 0019_knowledge_upload_dedupe
Revises: 0018_event_topics_catalog
Create Date: 2026-08-15
"""

import hashlib
import re
import uuid
from collections.abc import Sequence
from datetime import date
from html import unescape

import sqlalchemy as sa

from alembic import op

revision: str = "0019_knowledge_upload_dedupe"
down_revision: str | None = "0018_event_topics_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_upload_candidates",
        sa.Column("dedupe_fingerprint", sa.String(length=180), nullable=True),
    )
    op.add_column(
        "partner_updates",
        sa.Column("dedupe_fingerprint", sa.String(length=180), nullable=True),
    )
    op.add_column(
        "topic_updates",
        sa.Column("dedupe_fingerprint", sa.String(length=180), nullable=True),
    )
    op.create_index(
        op.f("ix_knowledge_upload_candidates_dedupe_fingerprint"),
        "knowledge_upload_candidates",
        ["dedupe_fingerprint"],
    )
    op.create_index(
        op.f("ix_partner_updates_dedupe_fingerprint"),
        "partner_updates",
        ["dedupe_fingerprint"],
    )
    op.create_index(
        op.f("ix_topic_updates_dedupe_fingerprint"),
        "topic_updates",
        ["dedupe_fingerprint"],
    )

    _backfill_partner_update_fingerprints()
    _backfill_topic_update_fingerprints()

    op.create_index(
        "ix_partner_updates_approved_dedupe_fingerprint",
        "partner_updates",
        ["dedupe_fingerprint"],
        unique=True,
        postgresql_where=sa.text(
            "dedupe_fingerprint IS NOT NULL AND status = 'approved'"
        ),
    )
    op.create_index(
        "ix_topic_updates_approved_dedupe_fingerprint",
        "topic_updates",
        ["dedupe_fingerprint"],
        unique=True,
        postgresql_where=sa.text(
            "dedupe_fingerprint IS NOT NULL AND status = 'approved'"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_topic_updates_approved_dedupe_fingerprint",
        table_name="topic_updates",
    )
    op.drop_index(
        "ix_partner_updates_approved_dedupe_fingerprint",
        table_name="partner_updates",
    )
    op.drop_index(op.f("ix_topic_updates_dedupe_fingerprint"), table_name="topic_updates")
    op.drop_index(op.f("ix_partner_updates_dedupe_fingerprint"), table_name="partner_updates")
    op.drop_index(
        op.f("ix_knowledge_upload_candidates_dedupe_fingerprint"),
        table_name="knowledge_upload_candidates",
    )
    op.drop_column("topic_updates", "dedupe_fingerprint")
    op.drop_column("partner_updates", "dedupe_fingerprint")
    op.drop_column("knowledge_upload_candidates", "dedupe_fingerprint")


def _backfill_partner_update_fingerprints() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT update_id, partner_id, cycle_month, summary
            FROM partner_updates
            WHERE status = 'approved'
            """
        )
    ).mappings()
    seen: set[str] = set()
    for row in rows:
        fingerprint = _build_fingerprint(
            "partner",
            row["partner_id"],
            row["cycle_month"],
            row["summary"],
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        connection.execute(
            sa.text(
                """
                UPDATE partner_updates
                SET dedupe_fingerprint = :fingerprint
                WHERE update_id = :update_id
                """
            ),
            {"fingerprint": fingerprint, "update_id": row["update_id"]},
        )


def _backfill_topic_update_fingerprints() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT topic_update_id, topic_id, topic_label, cycle_month, summary
            FROM topic_updates
            WHERE status = 'approved'
            """
        )
    ).mappings()
    seen: set[str] = set()
    for row in rows:
        topic_key = row["topic_id"] or _normalize_spacing(str(row["topic_label"]).lower())[:180]
        fingerprint = _build_fingerprint(
            "topic",
            topic_key,
            row["cycle_month"],
            row["summary"],
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        connection.execute(
            sa.text(
                """
                UPDATE topic_updates
                SET dedupe_fingerprint = :fingerprint
                WHERE topic_update_id = :topic_update_id
                """
            ),
            {"fingerprint": fingerprint, "topic_update_id": row["topic_update_id"]},
        )


def _build_fingerprint(
    target_kind: str,
    target_key: str | uuid.UUID,
    cycle_month: date,
    summary: str,
) -> str:
    normalized_summary = _normalize_update_content(summary)
    digest = hashlib.sha256(normalized_summary.encode("utf-8")).hexdigest()
    cycle_key = cycle_month.strftime("%Y-%m")
    return f"{target_kind}:{target_key}:cycle:{cycle_key}:content:{digest}"


def _normalize_update_content(value: str) -> str:
    text = re.sub(
        r"(?is)<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        lambda match: f" {_strip_tags(match.group(2))} [link:{unescape(match.group(1))}] ",
        value,
    )
    text = re.sub(r"(?i)<br\s*/?>", " ", text)
    text = re.sub(r"(?i)</(?:p|li|div|h[1-6]|ul|ol)>", " ", text)
    text = re.sub(r"(?i)<li[^>]*>", " ", text)
    text = _strip_tags(text)
    return _normalize_spacing(unescape(text).lower())


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def _normalize_spacing(value: str) -> str:
    return " ".join(value.split())
