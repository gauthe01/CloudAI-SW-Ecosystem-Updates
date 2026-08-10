import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.connected_source import ConnectedSource, ConnectedSourceStatus
from app.db.models.identity import RoleType, User, UserRoleAssignment, UserSession
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.source_event import (
    AgentRun,
    AgentRunStatus,
    SourceEvent,
    SourceEventStatus,
    SourcePayload,
    SourcePayloadRetentionPolicy,
)
from app.db.session import get_session_factory
from app.domains.contributor.connected_sources.schemas import ConnectedSourceRequest
from app.domains.contributor.connected_sources.service import ContributorConnectedSourceService
from app.domains.identity.service import user_to_response
from app.domains.source_events.schemas import SourceEventIngestRequest
from app.domains.source_events.service import SourceEventQueueService


@pytest.mark.asyncio
async def test_source_event_enqueue_is_idempotent_and_stores_payload_once() -> None:
    contributor_email = f"queue-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Queue Partner {uuid.uuid4()}"
    event_timestamp = datetime(2026, 8, 7, 10, 30, tzinfo=UTC)

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [contributor_email])
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="jira_issue",
                source_url="https://jira.example.com/browse/AWS-1500",
            ),
        )
        service = SourceEventQueueService(session)

        first = await service.enqueue_event(
            SourceEventIngestRequest(
                connected_source_id=source.connected_source_id,
                external_event_id="jira-event-1500",
                source_event_timestamp=event_timestamp,
                raw_payload_json={"issue": {"key": "AWS-1500"}},
            )
        )
        duplicate = await service.enqueue_event(
            SourceEventIngestRequest(
                connected_source_id=source.connected_source_id,
                external_event_id="jira-event-1500",
                source_event_timestamp=event_timestamp,
                raw_payload_json={"issue": {"key": "AWS-1500", "changed": True}},
            )
        )

        assert first.is_duplicate is False
        assert duplicate.is_duplicate is True
        assert duplicate.source_event.source_event_id == first.source_event.source_event_id

        result = await session.execute(select(SourcePayload))
        payloads = list(result.scalars().all())
        assert len(payloads) == 1
        assert payloads[0].raw_payload_json == {"issue": {"key": "AWS-1500"}}

        await cleanup_test_records(session, [partner_name], [contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_source_events_require_active_connected_source() -> None:
    contributor_email = f"queue-inactive-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Queue Inactive Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [contributor_email])
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="jira_issue",
                source_url="https://jira.example.com/browse/AWS-1501",
            ),
        )
        source.status = ConnectedSourceStatus.pending.value
        await session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await SourceEventQueueService(session).enqueue_event(
                SourceEventIngestRequest(
                    connected_source_id=source.connected_source_id,
                    external_event_id="inactive-event",
                )
            )

        assert exc_info.value.status_code == 409

        await cleanup_test_records(session, [partner_name], [contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_worker_default_processing_succeeds_and_logs_agent_run() -> None:
    contributor_email = f"queue-worker-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Queue Worker Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [contributor_email])
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="github_issue",
                source_url="https://github.com/arm/example/issues/1502",
            ),
        )
        service = SourceEventQueueService(session)
        queued = await service.enqueue_event(
            SourceEventIngestRequest(
                connected_source_id=source.connected_source_id,
                external_event_id="github-event-1502",
                raw_payload_json={"action": "opened"},
            )
        )

        processed = await service.process_next_event()

        assert processed.processed is True
        assert processed.status == SourceEventStatus.succeeded
        assert processed.source_event is not None
        assert processed.source_event.source_event_id == queued.source_event.source_event_id
        assert processed.source_event.attempt_count == 1

        result = await session.execute(select(AgentRun))
        agent_runs = list(result.scalars().all())
        assert len(agent_runs) == 1
        assert agent_runs[0].status == AgentRunStatus.succeeded.value
        assert agent_runs[0].rulebook_name == "source_event.github"
        assert agent_runs[0].rulebook_version.startswith("placeholder-2026-08-09:")
        assert agent_runs[0].output_json["pending_updates_created"] == 0
        assert agent_runs[0].output_json["extraction_mode"] == "infrastructure_only"

        await cleanup_test_records(session, [partner_name], [contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_worker_failure_retries_then_dead_letters() -> None:
    contributor_email = f"queue-failure-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Queue Failure Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [contributor_email])
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="confluence_page",
                source_url="https://confluence.example.com/display/AWS/Failure",
            ),
        )
        service = SourceEventQueueService(session)
        queued = await service.enqueue_event(
            SourceEventIngestRequest(
                connected_source_id=source.connected_source_id,
                external_event_id="confluence-event-failure",
                max_attempts=2,
            )
        )

        async def failing_handler(_event, _payload):
            raise RuntimeError("Extractor unavailable")

        first_failure = await service.process_event(
            queued.source_event.source_event_id,
            handler=failing_handler,
        )
        second_failure = await service.process_event(
            queued.source_event.source_event_id,
            handler=failing_handler,
        )

        assert first_failure.status == SourceEventStatus.retrying
        assert first_failure.source_event is not None
        assert first_failure.source_event.attempt_count == 1
        assert second_failure.status == SourceEventStatus.dead_letter
        assert second_failure.source_event is not None
        assert second_failure.source_event.attempt_count == 2

        result = await session.execute(select(AgentRun).order_by(AgentRun.started_at.asc()))
        agent_runs = list(result.scalars().all())
        assert [run.status for run in agent_runs] == [
            AgentRunStatus.failed.value,
            AgentRunStatus.failed.value,
        ]

        await cleanup_test_records(session, [partner_name], [contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_slack_events_store_technical_payload_record_without_raw_content() -> None:
    contributor_email = f"queue-slack-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Queue Slack Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [contributor_email])
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="slack_channel",
                channel_name="#queue-slack",
                channel_id="CQUEUE1503",
                bot_invited_confirmed=True,
            ),
        )

        await SourceEventQueueService(session).enqueue_event(
            SourceEventIngestRequest(
                connected_source_id=source.connected_source_id,
                external_event_id="slack-event-1503",
                technical_metadata={"channel_id": "CQUEUE1503", "message_ts": "123.456"},
                raw_payload_json={"text": "raw text must not be retained"},
                raw_text_encrypted="raw text must not be retained",
            )
        )

        result = await session.execute(select(SourcePayload))
        payload = result.scalar_one()
        assert payload.raw_payload_json is None
        assert payload.raw_text_encrypted is None
        assert (
            payload.retention_policy
            == SourcePayloadRetentionPolicy.technical_metadata_only.value
        )

        await cleanup_test_records(session, [partner_name], [contributor_email])
        await session.commit()


async def create_active_source(
    session: AsyncSession,
    *,
    partner_name: str,
    contributor_email: str,
    payload: ConnectedSourceRequest,
) -> ConnectedSource:
    contributor = User(email=contributor_email, display_name="Queue Contributor")
    contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
    partner = Partner(
        name=partner_name,
        description="Queue partner",
        status=PartnerStatus.active.value,
    )
    session.add_all([contributor, partner])
    await session.flush()
    session.add(
        PartnerContributorAssignment(
            partner_id=partner.partner_id,
            user_id=contributor.user_id,
        )
    )
    await session.commit()

    source_response = await ContributorConnectedSourceService(session).create_source(
        partner_id=partner.partner_id,
        payload=payload,
        current_user=user_to_response(contributor),
    )
    result = await session.execute(
        select(ConnectedSource).where(
            ConnectedSource.connected_source_id == source_response.connected_source_id
        )
    )
    source = result.scalar_one()
    source.status = ConnectedSourceStatus.active.value
    await session.commit()
    return source


async def cleanup_test_records(
    session: AsyncSession,
    partner_names: list[str],
    emails: list[str],
) -> None:
    partner_ids = select_partner_ids(partner_names)
    await session.execute(delete(AgentRun))
    await session.execute(delete(SourcePayload))
    await session.execute(
        delete(SourceEvent).where(SourceEvent.partner_id.in_(partner_ids))
    )
    await session.execute(
        delete(ConnectedSource).where(ConnectedSource.partner_id.in_(partner_ids))
    )
    await session.execute(
        delete(PartnerContributorAssignment).where(
            PartnerContributorAssignment.partner_id.in_(partner_ids)
        )
    )
    await session.execute(delete(Partner).where(Partner.name.in_(partner_names)))
    await session.execute(
        delete(UserSession).where(UserSession.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(delete(User).where(User.email.in_(emails)))


def select_partner_ids(partner_names: list[str]):
    return select(Partner.partner_id).where(Partner.name.in_(partner_names))


def select_user_ids(emails: list[str]):
    return select(User.user_id).where(User.email.in_(emails))
