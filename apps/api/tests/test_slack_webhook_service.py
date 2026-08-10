import hashlib
import hmac
import json
import time
import uuid

import httpx
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
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.db.models.source_event import AgentRun, SourceEvent, SourcePayload
from app.db.session import get_session_factory
from app.domains.admin.integrations.schemas import IntegrationCredentialUpdateRequest
from app.domains.admin.integrations.service import AdminIntegrationService
from app.domains.contributor.connected_sources.schemas import ConnectedSourceRequest
from app.domains.contributor.connected_sources.service import ContributorConnectedSourceService
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.service import user_to_response
from app.domains.webhooks.slack.security import verify_slack_signature
from app.main import create_app

SLACK_SIGNING_SECRET = "test-slack-signing-secret"


def test_verify_slack_signature_accepts_valid_signature_and_rejects_invalid() -> None:
    raw_body = b'{"type":"event_callback"}'
    timestamp = str(int(time.time()))
    signature = sign_slack_body(raw_body, timestamp)

    assert verify_slack_signature(
        signing_secret=SLACK_SIGNING_SECRET,
        raw_body=raw_body,
        timestamp=timestamp,
        signature=signature,
    )
    assert not verify_slack_signature(
        signing_secret=SLACK_SIGNING_SECRET,
        raw_body=raw_body,
        timestamp=timestamp,
        signature="v0=invalid",
    )


@pytest.mark.asyncio
async def test_slack_url_verification_returns_challenge() -> None:
    admin_email = f"slack-url-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await configure_slack_integration(session, admin_email)

    payload = {"type": "url_verification", "challenge": "challenge-token"}
    response = await post_slack_payload(payload)

    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-token"}

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_slack_event_for_active_channel_creates_pending_update_without_raw_storage() -> None:
    admin_email = f"slack-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"slack-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Slack Partner {uuid.uuid4()}"
    channel_id = f"C{uuid.uuid4().hex[:10].upper()}"
    slack_text = "AWS release milestone is blocked by partner validation risk."

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_slack_integration(session, admin_email)
        await create_active_slack_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            channel_id=channel_id,
        )

    payload = slack_event_payload(
        channel_id=channel_id,
        event_id=f"Ev{uuid.uuid4().hex}",
        text=slack_text,
    )
    response = await post_slack_payload(payload)

    assert response.status_code == 200
    assert response.json()["status"] == "processed"

    async with get_session_factory()() as session:
        source_events = list((await session.execute(select(SourceEvent))).scalars().all())
        payloads = list((await session.execute(select(SourcePayload))).scalars().all())
        updates = list((await session.execute(select(PartnerUpdate))).scalars().all())

        assert len(source_events) == 1
        assert source_events[0].external_event_id == payload["event_id"]
        assert source_events[0].technical_metadata["channel_id"] == channel_id
        assert slack_text not in json.dumps(source_events[0].technical_metadata)

        assert len(payloads) == 1
        assert payloads[0].raw_payload_json is None
        assert payloads[0].raw_text_encrypted is None

        assert len(updates) == 1
        assert updates[0].status == PartnerUpdateStatus.pending.value
        assert updates[0].source_type == "slack"
        assert updates[0].source_url == f"https://slack.com/app_redirect?channel={channel_id}"
        assert updates[0].source_event_id == source_events[0].source_event_id

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_slack_duplicate_event_does_not_create_duplicate_pending_update() -> None:
    admin_email = f"slack-duplicate-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"slack-duplicate-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Slack Duplicate Partner {uuid.uuid4()}"
    channel_id = f"C{uuid.uuid4().hex[:10].upper()}"
    event_id = f"Ev{uuid.uuid4().hex}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_slack_integration(session, admin_email)
        await create_active_slack_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            channel_id=channel_id,
        )

    payload = slack_event_payload(
        channel_id=channel_id,
        event_id=event_id,
        text="Partner decision update needs review for AWS enablement.",
    )
    first_response = await post_slack_payload(payload)
    second_response = await post_slack_payload(payload)

    assert first_response.json()["status"] == "processed"
    assert second_response.json()["status"] == "duplicate"

    async with get_session_factory()() as session:
        event_count = (await session.execute(select(SourceEvent))).scalars().all()
        update_count = (await session.execute(select(PartnerUpdate))).scalars().all()
        assert len(event_count) == 1
        assert len(update_count) == 1

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_slack_event_for_unmapped_channel_is_ignored() -> None:
    admin_email = f"slack-unmapped-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await configure_slack_integration(session, admin_email)

    response = await post_slack_payload(
        slack_event_payload(
            channel_id="CUNMAPPED01",
            event_id=f"Ev{uuid.uuid4().hex}",
            text="This should not enqueue because the channel is unmapped.",
        )
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

    async with get_session_factory()() as session:
        assert list((await session.execute(select(SourceEvent))).scalars().all()) == []
        await cleanup_test_records(session, [], [admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_slack_webhook_rejects_invalid_signature() -> None:
    admin_email = f"slack-invalid-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await configure_slack_integration(session, admin_email)

    raw_body = json.dumps({"type": "event_callback", "event": {}}).encode()
    timestamp = str(int(time.time()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/webhooks/slack/events",
            content=raw_body,
            headers={
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": "v0=invalid",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 401

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await session.commit()


async def configure_slack_integration(session: AsyncSession, admin_email: str) -> None:
    repository = IdentityRepository(session)
    admin = repository.add_user_with_local_password(
        email=admin_email,
        display_name="Slack Admin",
        password_hash=hash_password("test-password"),
        roles=[RoleType.admin],
    )
    await session.commit()
    service = AdminIntegrationService(session, get_settings())
    await service.update_credentials(
        integration_type=IntegrationType.slack,
        payload=IntegrationCredentialUpdateRequest(
            secrets={
                "signing_secret": SLACK_SIGNING_SECRET,
                "bot_token": "xoxb-test-token",
            }
        ),
        current_admin=user_to_response(admin),
    )
    await service.test_integration(
        integration_type=IntegrationType.slack,
        current_admin=user_to_response(admin),
    )


async def create_active_slack_source(
    session: AsyncSession,
    *,
    partner_name: str,
    contributor_email: str,
    channel_id: str,
) -> ConnectedSource:
    contributor = User(email=contributor_email, display_name="Slack Contributor")
    contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
    partner = Partner(
        name=partner_name,
        description="Slack partner",
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
        payload=ConnectedSourceRequest(
            source_type="slack_channel",
            channel_name="#aws-slack",
            channel_id=channel_id,
            bot_invited_confirmed=True,
        ),
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


def slack_event_payload(*, channel_id: str, event_id: str, text: str) -> dict:
    return {
        "type": "event_callback",
        "event_id": event_id,
        "event_time": 1786132000,
        "event": {
            "type": "message",
            "channel": channel_id,
            "user": "U123456",
            "text": text,
            "ts": "1786132000.000100",
        },
    }


async def post_slack_payload(payload: dict) -> httpx.Response:
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="http://testserver",
    ) as client:
        return await client.post(
            "/api/webhooks/slack/events",
            content=raw_body,
            headers={
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": sign_slack_body(raw_body, timestamp),
                "Content-Type": "application/json",
            },
        )


def sign_slack_body(raw_body: bytes, timestamp: str) -> str:
    base_string = b"v0:" + timestamp.encode() + b":" + raw_body
    return "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        base_string,
        hashlib.sha256,
    ).hexdigest()


async def cleanup_test_records(
    session: AsyncSession,
    partner_names: list[str],
    emails: list[str],
) -> None:
    partner_ids = select_partner_ids(partner_names)
    await session.execute(delete(AgentRun))
    await session.execute(delete(SourcePayload))
    await session.execute(delete(PartnerUpdate).where(PartnerUpdate.partner_id.in_(partner_ids)))
    await session.execute(delete(SourceEvent).where(SourceEvent.partner_id.in_(partner_ids)))
    await session.execute(
        delete(ConnectedSource).where(ConnectedSource.partner_id.in_(partner_ids))
    )
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
