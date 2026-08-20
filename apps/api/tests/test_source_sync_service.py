import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models.connected_source import ConnectedSource, ConnectedSourceStatus
from app.db.models.identity import (
    RoleType,
    User,
    UserLocalCredential,
    UserRoleAssignment,
    UserSession,
)
from app.db.models.integration import (
    Integration,
    IntegrationSecret,
    IntegrationTestRun,
    IntegrationType,
)
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.source_event import AgentRun, SourceEvent, SourcePayload
from app.db.models.source_sync import SourceSyncRun, SourceSyncRunStatus, SourceSyncState
from app.db.session import get_session_factory
from app.domains.admin.integrations.schemas import IntegrationCredentialUpdateRequest
from app.domains.admin.integrations.service import AdminIntegrationService
from app.domains.contributor.connected_sources.schemas import ConnectedSourceRequest
from app.domains.contributor.connected_sources.service import ContributorConnectedSourceService
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.service import user_to_response
from app.domains.source_sync.connectors import JiraSourceSyncConnector, SlackSourceSyncConnector
from app.domains.source_sync.service import SourceSyncService


@pytest.mark.asyncio
async def test_slack_source_sync_enqueues_new_messages_and_records_cursor(monkeypatch) -> None:
    admin_email = f"sync-slack-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"sync-slack-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Sync Slack Partner {uuid.uuid4()}"
    channel_id = f"C{uuid.uuid4().hex[:10].upper()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_integration(
            session,
            admin_email=admin_email,
            integration_type=IntegrationType.slack,
            secrets={"signing_secret": "secret", "bot_token": "xoxb-test-token"},
        )
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="slack_channel",
                channel_name="#partner-sync",
                channel_id=channel_id,
                bot_invited_confirmed=True,
            ),
        )

        history_calls: list[tuple[str | None, str | None]] = []

        async def fake_history(
            self,
            *,
            bot_token: str,
            channel_id: str,
            oldest: str | None,
            latest: str | None = None,
            cursor: str | None = None,
        ):
            history_calls.append((oldest, cursor))
            if cursor == "older-page":
                return {
                    "ok": True,
                    "messages": [
                        {
                            "type": "message",
                            "user": "U222",
                            "text": "The August enablement checkpoint moved one week earlier.",
                            "ts": "1785456000.000100",
                        }
                    ],
                    "response_metadata": {"next_cursor": ""},
                }
            return {
                "ok": True,
                "messages": [
                    {
                        "type": "message",
                        "user": "U111",
                        "text": "Partner confirmed 4 QS A1 systems for October benchmarking.",
                        "ts": "1785542400.000200",
                    },
                    {
                        "type": "message",
                        "subtype": "channel_join",
                        "text": "Someone joined.",
                        "ts": "1785455000.000100",
                    },
                ],
                "response_metadata": {"next_cursor": "older-page"},
            }

        monkeypatch.setattr(SlackSourceSyncConnector, "_get_history", fake_history)
        result = await SourceSyncService(session, get_settings()).sync_source(
            source.connected_source_id
        )

        assert result.fetched == 2
        assert result.queued == 2
        assert result.ignored == 1
        assert history_calls == [(None, None), (None, "older-page")]

        events = list(
            (
                await session.execute(
                    select(SourceEvent).order_by(SourceEvent.source_event_timestamp.asc())
                )
            )
            .scalars()
            .all()
        )
        payloads = list((await session.execute(select(SourcePayload))).scalars().all())
        state = await session.get(SourceSyncState, source.connected_source_id)
        run = (await session.execute(select(SourceSyncRun))).scalar_one()

        assert [event.external_event_id for event in events] == [
            f"{channel_id}:1785456000.000100",
            f"{channel_id}:1785542400.000200",
        ]
        assert events[0].source_event_timestamp.month == 7
        assert payloads[0].raw_payload_json is not None
        assert "source_item" in payloads[0].raw_payload_json
        assert state is not None
        assert state.cursor_value == "1785542400.000200"
        assert state.backfill_completed_at is not None
        assert run.status == SourceSyncRunStatus.succeeded.value

        history_calls.clear()

        async def fake_incremental_history(
            self,
            *,
            bot_token: str,
            channel_id: str,
            oldest: str | None,
            latest: str | None = None,
            cursor: str | None = None,
        ):
            history_calls.append((oldest, cursor))
            return {"ok": True, "messages": [], "response_metadata": {"next_cursor": ""}}

        monkeypatch.setattr(SlackSourceSyncConnector, "_get_history", fake_incremental_history)
        second_result = await SourceSyncService(session, get_settings()).sync_source(
            source.connected_source_id
        )

        assert second_result.fetched == 0
        assert second_result.queued == 0
        assert history_calls == [("1785542400.000200", None)]

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_existing_slack_source_backfills_before_existing_cursor(monkeypatch) -> None:
    admin_email = f"sync-slack-backfill-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"sync-slack-backfill-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Sync Slack Backfill Partner {uuid.uuid4()}"
    channel_id = f"C{uuid.uuid4().hex[:10].upper()}"
    existing_cursor = "1785542400.000200"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_integration(
            session,
            admin_email=admin_email,
            integration_type=IntegrationType.slack,
            secrets={"signing_secret": "secret", "bot_token": "xoxb-test-token"},
        )
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="slack_channel",
                channel_name="#existing-source",
                channel_id=channel_id,
                bot_invited_confirmed=True,
            ),
        )
        session.add(
            SourceSyncState(
                connected_source_id=source.connected_source_id,
                cursor_value=existing_cursor,
                cursor_timestamp=datetime.fromtimestamp(float(existing_cursor), UTC),
            )
        )
        await session.commit()

        history_calls: list[tuple[str | None, str | None, str | None]] = []

        async def fake_history(
            self,
            *,
            bot_token: str,
            channel_id: str,
            oldest: str | None,
            latest: str | None = None,
            cursor: str | None = None,
        ):
            history_calls.append((oldest, latest, cursor))
            return {
                "ok": True,
                "messages": [
                    {
                        "type": "message",
                        "user": "U222",
                        "text": "Historic partner message before existing cursor.",
                        "ts": "1785456000.000100",
                    }
                ],
                "response_metadata": {"next_cursor": ""},
            }

        monkeypatch.setattr(SlackSourceSyncConnector, "_get_history", fake_history)
        result = await SourceSyncService(session, get_settings()).sync_source(
            source.connected_source_id
        )

        state = await session.get(SourceSyncState, source.connected_source_id)

        assert result.fetched == 1
        assert result.queued == 1
        assert history_calls == [(None, existing_cursor, None)]
        assert state is not None
        assert state.cursor_value == existing_cursor
        assert state.backfill_completed_at is not None

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_jira_source_sync_enqueues_comments_and_changelog_after_cursor(monkeypatch) -> None:
    admin_email = f"sync-jira-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"sync-jira-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Sync Jira Partner {uuid.uuid4()}"
    issue_key = "STESOL-431"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_integration(
            session,
            admin_email=admin_email,
            integration_type=IntegrationType.jira,
            secrets={
                "base_url": "https://jira.example.com",
                "service_token": "test-jira-token",
                "webhook_secret": "test-secret",
            },
        )
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="jira_issue",
                source_url=f"https://jira.example.com/browse/{issue_key}",
            ),
        )
        session.add(
            SourceSyncState(
                connected_source_id=source.connected_source_id,
                cursor_value="2026-06-01T00:00:00+00:00",
                cursor_timestamp=datetime(2026, 6, 1, tzinfo=UTC),
                backfill_completed_at=datetime(2026, 6, 1, tzinfo=UTC),
            )
        )
        await session.commit()

        async def fake_issue(self, *, base_url: str, token: str, issue_key: str):
            return {
                "key": issue_key,
                "fields": {
                    "summary": "SAP HANA Cloud monthly progress",
                    "comment": {
                        "comments": [
                            {
                                "id": "101",
                                "created": "2026-05-05T10:00:00.000+0000",
                                "body": "Old May context should not be fetched again.",
                            },
                            {
                                "id": "102",
                                "created": "2026-07-01T21:46:00.000+0000",
                                "body": (
                                    "Initial full repository expected in ~6 weeks. "
                                    "No major blockers identified."
                                ),
                            },
                        ]
                    },
                },
                "changelog": {
                    "histories": [
                        {
                            "id": "201",
                            "created": "2026-07-02T11:13:00.000+0000",
                            "items": [
                                {
                                    "field": "priority",
                                    "fromString": "Minor",
                                    "toString": "Major",
                                }
                            ],
                        }
                    ]
                },
            }

        monkeypatch.setattr(JiraSourceSyncConnector, "_fetch_issue", fake_issue)
        result = await SourceSyncService(session, get_settings()).sync_source(
            source.connected_source_id
        )

        assert result.fetched == 2
        assert result.queued == 2
        events = list(
            (
                await session.execute(
                    select(SourceEvent).order_by(SourceEvent.source_event_timestamp.asc())
                )
            )
            .scalars()
            .all()
        )
        assert [event.external_event_id for event in events] == [
            f"{issue_key}:comment:102",
            f"{issue_key}:changelog:201",
        ]
        assert all(event.source_event_timestamp.month == 7 for event in events)

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_jira_source_sync_backfills_full_issue_history_and_records_cursor(
    monkeypatch,
) -> None:
    admin_email = f"sync-jira-backfill-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"sync-jira-backfill-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Sync Jira Backfill Partner {uuid.uuid4()}"
    issue_key = "STESOL-777"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_integration(
            session,
            admin_email=admin_email,
            integration_type=IntegrationType.jira,
            secrets={
                "base_url": "https://jira.example.com",
                "service_token": "test-jira-token",
                "webhook_secret": "test-secret",
            },
        )
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="jira_issue",
                source_url=f"https://jira.example.com/browse/{issue_key}",
            ),
        )

        async def fake_issue(self, *, base_url: str, token: str, issue_key: str):
            return {
                "key": issue_key,
                "fields": {
                    "summary": "SAP HANA Cloud readiness issue",
                    "created": "2026-03-04T09:00:00.000+0000",
                    "updated": "2026-07-02T11:13:00.000+0000",
                    "description": "Initial AGI CPU readiness tracking for SAP HANA Cloud.",
                    "comment": {
                        "comments": [
                            {
                                "id": "301",
                                "created": "2026-05-05T10:00:00.000+0000",
                                "body": "May certification inputs are ready for review.",
                            },
                            {
                                "id": "302",
                                "created": "2026-07-01T21:46:00.000+0000",
                                "body": "July validation now targets a CRB package in Aug./Sept.",
                            },
                        ]
                    },
                },
                "changelog": {
                    "histories": [
                        {
                            "id": "401",
                            "created": "2026-04-10T12:00:00.000+0000",
                            "items": [{"field": "description"}],
                        }
                    ]
                },
            }

        monkeypatch.setattr(JiraSourceSyncConnector, "_fetch_issue", fake_issue)
        result = await SourceSyncService(session, get_settings()).sync_source(
            source.connected_source_id
        )

        assert result.fetched == 3
        assert result.queued == 3
        events = list(
            (
                await session.execute(
                    select(SourceEvent).order_by(SourceEvent.source_event_timestamp.asc())
                )
            )
            .scalars()
            .all()
        )
        state = await session.get(SourceSyncState, source.connected_source_id)

        assert [event.source_event_timestamp.month for event in events] == [4, 5, 7]
        assert [event.technical_metadata["event_type"] for event in events] == [
            "description",
            "comment",
            "comment",
        ]
        assert state is not None
        assert state.cursor_timestamp == datetime(2026, 7, 1, 21, 46, tzinfo=UTC)
        assert state.backfill_completed_at is not None

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_existing_jira_source_backfills_before_existing_cursor(monkeypatch) -> None:
    admin_email = f"sync-jira-legacy-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"sync-jira-legacy-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Sync Jira Legacy Backfill Partner {uuid.uuid4()}"
    issue_key = "STESOL-888"
    cursor_timestamp = datetime(2026, 7, 1, tzinfo=UTC)
    cursor_value = cursor_timestamp.isoformat()

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_integration(
            session,
            admin_email=admin_email,
            integration_type=IntegrationType.jira,
            secrets={
                "base_url": "https://jira.example.com",
                "service_token": "test-jira-token",
                "webhook_secret": "test-secret",
            },
        )
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="jira_issue",
                source_url=f"https://jira.example.com/browse/{issue_key}",
            ),
        )
        session.add(
            SourceSyncState(
                connected_source_id=source.connected_source_id,
                cursor_value=cursor_value,
                cursor_timestamp=cursor_timestamp,
            )
        )
        await session.commit()

        async def fake_issue(self, *, base_url: str, token: str, issue_key: str):
            return {
                "key": issue_key,
                "fields": {
                    "summary": "Legacy Jira source",
                    "comment": {
                        "comments": [
                            {
                                "id": "501",
                                "created": "2026-05-15T10:00:00.000+0000",
                                "body": "Historic May Jira comment should be backfilled.",
                            },
                            {
                                "id": "502",
                                "created": "2026-08-15T10:00:00.000+0000",
                                "body": (
                                    "Future incremental comment should wait for cursor polling."
                                ),
                            },
                        ]
                    },
                },
                "changelog": {"histories": []},
            }

        monkeypatch.setattr(JiraSourceSyncConnector, "_fetch_issue", fake_issue)
        result = await SourceSyncService(session, get_settings()).sync_source(
            source.connected_source_id
        )

        assert result.fetched == 1
        assert result.queued == 1
        events = list((await session.execute(select(SourceEvent))).scalars().all())
        state = await session.get(SourceSyncState, source.connected_source_id)

        assert events[0].external_event_id == f"{issue_key}:comment:501"
        assert events[0].source_event_timestamp.month == 5
        assert state is not None
        assert state.cursor_value == cursor_value
        assert state.cursor_timestamp == cursor_timestamp
        assert state.backfill_completed_at is not None

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_source_sync_skips_disabled_sources() -> None:
    admin_email = f"sync-disabled-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"sync-disabled-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Sync Disabled Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_integration(
            session,
            admin_email=admin_email,
            integration_type=IntegrationType.slack,
            secrets={"signing_secret": "secret", "bot_token": "xoxb-test-token"},
        )
        source = await create_active_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            payload=ConnectedSourceRequest(
                source_type="slack_channel",
                channel_name="#disabled",
                channel_id="CDISABLED",
                bot_invited_confirmed=True,
            ),
        )
        source.status = ConnectedSourceStatus.disabled.value
        await session.commit()

        result = await SourceSyncService(session, get_settings()).run_due_sources()

        assert result.processed == 0
        assert list((await session.execute(select(SourceEvent))).scalars().all()) == []

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


async def configure_integration(
    session: AsyncSession,
    *,
    admin_email: str,
    integration_type: IntegrationType,
    secrets: dict[str, str],
) -> None:
    repository = IdentityRepository(session)
    admin = repository.add_user_with_local_password(
        email=admin_email,
        display_name="Sync Admin",
        password_hash=hash_password("test-password"),
        roles=[RoleType.admin],
    )
    await session.commit()
    service = AdminIntegrationService(session, get_settings())
    await service.update_credentials(
        integration_type=integration_type,
        payload=IntegrationCredentialUpdateRequest(secrets=secrets),
        current_admin=user_to_response(admin),
    )
    await service.test_integration(
        integration_type=integration_type,
        current_admin=user_to_response(admin),
    )


async def create_active_source(
    session: AsyncSession,
    *,
    partner_name: str,
    contributor_email: str,
    payload: ConnectedSourceRequest,
) -> ConnectedSource:
    contributor = User(email=contributor_email, display_name="Sync Contributor")
    contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
    partner = Partner(
        name=partner_name,
        description="Sync partner",
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

    response = await ContributorConnectedSourceService(session).create_source(
        partner_id=partner.partner_id,
        payload=payload,
        current_user=user_to_response(contributor),
    )
    result = await session.execute(
        select(ConnectedSource).where(
            ConnectedSource.connected_source_id == response.connected_source_id
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
    await session.execute(delete(SourceEvent))
    await session.execute(delete(SourceSyncRun))
    await session.execute(delete(SourceSyncState))
    await session.execute(delete(ConnectedSource))
    await session.execute(
        delete(PartnerContributorAssignment).where(
            PartnerContributorAssignment.partner_id.in_(partner_ids)
        )
    )
    await session.execute(delete(Partner).where(Partner.name.in_(partner_names)))
    await session.execute(delete(IntegrationTestRun))
    await session.execute(delete(IntegrationSecret))
    await session.execute(delete(Integration))
    await session.execute(
        delete(UserSession).where(UserSession.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserLocalCredential).where(UserLocalCredential.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(delete(User).where(User.email.in_(emails)))


def select_partner_ids(partner_names: list[str]):
    return select(Partner.partner_id).where(Partner.name.in_(partner_names))


def select_user_ids(emails: list[str]):
    return select(User.user_id).where(User.email.in_(emails))
