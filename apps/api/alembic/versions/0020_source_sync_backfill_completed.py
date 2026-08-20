"""source sync backfill completion marker

Revision ID: 0020_source_sync_backfill_completed
Revises: 0019_knowledge_upload_dedupe
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_source_sync_backfill_completed"
down_revision: str | None = "0019_knowledge_upload_dedupe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_sync_states",
        sa.Column("backfill_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    _requeue_legacy_infrastructure_only_slack_events()


def downgrade() -> None:
    op.drop_column("source_sync_states", "backfill_completed_at")


def _requeue_legacy_infrastructure_only_slack_events() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE source_events se
            SET processing_status = 'pending',
                attempt_count = 0,
                last_error_summary = NULL,
                processing_started_at = NULL,
                processed_at = NULL,
                next_retry_at = NULL
            WHERE se.source_type = 'slack_channel'
              AND se.processing_status = 'succeeded'
              AND NOT EXISTS (
                  SELECT 1
                  FROM partner_updates pu
                  WHERE pu.source_event_id = se.source_event_id
              )
              AND EXISTS (
                  SELECT 1
                  FROM source_payloads sp
                  WHERE sp.source_event_id = se.source_event_id
                    AND sp.raw_payload_json IS NOT NULL
              )
            """
        )
    )
