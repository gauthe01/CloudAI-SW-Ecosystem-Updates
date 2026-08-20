from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.connected_source import ConnectedSource, ConnectedSourceStatus
from app.db.models.source_sync import SourceSyncRun, SourceSyncRunStatus, SourceSyncState
from app.domains.source_events.service import SourceEventQueueService

from .connectors import ConnectorSyncResult, connector_for_source, to_ingest_request


@dataclass(frozen=True)
class SourceSyncSummary:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    fetched: int = 0
    queued: int = 0
    duplicates: int = 0
    ignored: int = 0


class SourceSyncService:
    def __init__(self, db: AsyncSession, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()

    async def run_due_sources(self, *, limit: int | None = None) -> SourceSyncSummary:
        if not self.settings.source_sync_enabled:
            return SourceSyncSummary()
        now = datetime.now(UTC)
        sources = await self._load_due_sources(
            now=now,
            limit=limit or self.settings.source_sync_batch_size,
        )
        summary = SourceSyncSummary()
        totals = summary.__dict__.copy()
        for source in sources:
            result = await self.sync_source(source.connected_source_id)
            totals["processed"] += 1
            for key in ("fetched", "queued", "duplicates", "ignored"):
                totals[key] += getattr(result, key)
            if result.skipped:
                totals["skipped"] += 1
            elif result.failed:
                totals["failed"] += 1
            else:
                totals["succeeded"] += 1
        return SourceSyncSummary(**totals)

    async def sync_source(self, connected_source_id: uuid.UUID) -> SourceSyncSummary:
        source = await self._load_active_source(connected_source_id)
        state = await self._get_or_create_state(source.connected_source_id)
        run = SourceSyncRun(
            connected_source_id=source.connected_source_id,
            source_type=source.source_type,
            status=SourceSyncRunStatus.running.value,
            started_at=datetime.now(UTC),
        )
        self.db.add(run)
        await self.db.flush()

        try:
            connector = connector_for_source(
                source_type=source.source_type,
                db=self.db,
                settings=self.settings,
            )
            connector_result = await connector.fetch(source=source, state=state)
            if connector_result.skipped_reason:
                return await self._finish_skipped(run, state, connector_result)
            return await self._enqueue_and_finish(source, state, run, connector_result)
        except Exception as exc:
            return await self._finish_failed(source, state, run, str(exc)[:1200])

    async def _load_due_sources(self, *, now: datetime, limit: int) -> list[ConnectedSource]:
        statement = (
            select(ConnectedSource)
            .outerjoin(
                SourceSyncState,
                SourceSyncState.connected_source_id == ConnectedSource.connected_source_id,
            )
            .where(ConnectedSource.status == ConnectedSourceStatus.active.value)
            .where((SourceSyncState.next_sync_at.is_(None)) | (SourceSyncState.next_sync_at <= now))
            .order_by(
                SourceSyncState.next_sync_at.asc().nullsfirst(),
                ConnectedSource.created_at.asc(),
            )
            .limit(limit)
        )
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def _load_active_source(self, connected_source_id: uuid.UUID) -> ConnectedSource:
        result = await self.db.execute(
            select(ConnectedSource)
            .where(ConnectedSource.connected_source_id == connected_source_id)
            .where(ConnectedSource.status == ConnectedSourceStatus.active.value)
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise RuntimeError("Active connected source not found.")
        return source

    async def _get_or_create_state(self, connected_source_id: uuid.UUID) -> SourceSyncState:
        result = await self.db.execute(
            select(SourceSyncState).where(
                SourceSyncState.connected_source_id == connected_source_id
            )
        )
        state = result.scalar_one_or_none()
        if state is not None:
            return state
        now = datetime.now(UTC)
        state = SourceSyncState(
            connected_source_id=connected_source_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(state)
        await self.db.flush()
        return state

    async def _enqueue_and_finish(
        self,
        source: ConnectedSource,
        state: SourceSyncState,
        run: SourceSyncRun,
        connector_result: ConnectorSyncResult,
    ) -> SourceSyncSummary:
        queued = 0
        duplicates = 0
        queue_service = SourceEventQueueService(self.db)
        for item in connector_result.items:
            response = await queue_service.enqueue_event(
                to_ingest_request(item, source.connected_source_id)
            )
            if response.is_duplicate:
                duplicates += 1
            else:
                queued += 1
        now = datetime.now(UTC)
        run.status = SourceSyncRunStatus.succeeded.value
        run.finished_at = now
        run.fetched_count = len(connector_result.items)
        run.queued_count = queued
        run.duplicate_count = duplicates
        run.ignored_count = connector_result.ignored_count
        state.cursor_value = connector_result.cursor_value
        state.cursor_timestamp = connector_result.cursor_timestamp
        state.last_synced_at = now
        state.last_successful_sync_at = now
        if connector_result.backfill_completed:
            state.backfill_completed_at = now
        state.next_sync_at = now + timedelta(seconds=self.settings.source_sync_interval_seconds)
        state.last_error_summary = None
        state.consecutive_failures = 0
        state.updated_at = now
        source.last_error_summary = None
        await self.db.commit()
        return SourceSyncSummary(
            processed=1,
            succeeded=1,
            fetched=len(connector_result.items),
            queued=queued,
            duplicates=duplicates,
            ignored=connector_result.ignored_count,
        )

    async def _finish_skipped(
        self,
        run: SourceSyncRun,
        state: SourceSyncState,
        connector_result: ConnectorSyncResult,
    ) -> SourceSyncSummary:
        now = datetime.now(UTC)
        run.status = SourceSyncRunStatus.skipped.value
        run.finished_at = now
        run.error_summary = connector_result.skipped_reason
        state.last_synced_at = now
        state.next_sync_at = now + timedelta(seconds=self.settings.source_sync_interval_seconds)
        state.updated_at = now
        await self.db.commit()
        return SourceSyncSummary(processed=1, skipped=1)

    async def _finish_failed(
        self,
        source: ConnectedSource,
        state: SourceSyncState,
        run: SourceSyncRun,
        error_summary: str,
    ) -> SourceSyncSummary:
        now = datetime.now(UTC)
        failures = state.consecutive_failures + 1
        retry_delay = min(3600, self.settings.source_sync_interval_seconds * failures)
        run.status = SourceSyncRunStatus.failed.value
        run.finished_at = now
        run.error_summary = error_summary
        state.last_synced_at = now
        state.next_sync_at = now + timedelta(seconds=retry_delay)
        state.last_error_summary = error_summary
        state.consecutive_failures = failures
        state.updated_at = now
        source.last_error_summary = error_summary
        await self.db.commit()
        return SourceSyncSummary(processed=1, failed=1)
