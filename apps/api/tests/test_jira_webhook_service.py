import hashlib
import hmac
import json
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
from app.domains.webhooks.jira.security import verify_jira_signature
from app.main import create_app

JIRA_WEBHOOK_SECRET = "test-jira-webhook-secret"


def test_verify_jira_signature_accepts_valid_signature_and_rejects_invalid() -> None:
    raw_body = b'{"webhookEvent":"jira:issue_updated"}'
    signature = sign_jira_body(raw_body)

    assert verify_jira_signature(
        webhook_secret=JIRA_WEBHOOK_SECRET,
        raw_body=raw_body,
        signature=signature,
    )
    assert not verify_jira_signature(
        webhook_secret=JIRA_WEBHOOK_SECRET,
        raw_body=raw_body,
        signature="sha256=invalid",
    )


@pytest.mark.asyncio
async def test_jira_event_for_active_issue_creates_pending_update_without_raw_storage() -> None:
    admin_email = f"jira-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"jira-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Jira Partner {uuid.uuid4()}"
    issue_key = "AWS-321"
    issue_summary = "Partner validation risk needs release decision"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_jira_integration(session, admin_email)
        await create_active_jira_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            issue_key=issue_key,
        )

    payload = jira_event_payload(issue_key=issue_key, issue_summary=issue_summary)
    response = await post_jira_payload(payload)

    assert response.status_code == 200
    assert response.json()["status"] == "processed"

    async with get_session_factory()() as session:
        source_events = list((await session.execute(select(SourceEvent))).scalars().all())
        payloads = list((await session.execute(select(SourcePayload))).scalars().all())
        updates = list((await session.execute(select(PartnerUpdate))).scalars().all())

        assert len(source_events) == 1
        assert source_events[0].external_event_id.startswith(f"jira:issue_updated:{issue_key}")
        assert source_events[0].technical_metadata["issue_key"] == issue_key
        assert issue_summary not in json.dumps(source_events[0].technical_metadata)

        assert len(payloads) == 1
        assert payloads[0].raw_payload_json is None
        assert payloads[0].raw_text_encrypted is None

        assert len(updates) == 1
        assert updates[0].status == PartnerUpdateStatus.pending.value
        assert updates[0].source_type == "jira"
        assert updates[0].source_label == issue_key
        assert updates[0].source_url == f"https://jira.example.com/browse/{issue_key}"
        assert updates[0].source_event_id == source_events[0].source_event_id
        assert issue_summary in updates[0].summary

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_jira_duplicate_event_does_not_create_duplicate_pending_update() -> None:
    admin_email = f"jira-duplicate-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"jira-duplicate-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Jira Duplicate Partner {uuid.uuid4()}"
    issue_key = "AWS-322"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_jira_integration(session, admin_email)
        await create_active_jira_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            issue_key=issue_key,
        )

    payload = jira_event_payload(issue_key=issue_key, issue_summary="Duplicate decision risk")
    first_response = await post_jira_payload(payload)
    second_response = await post_jira_payload(payload)

    assert first_response.json()["status"] == "processed"
    assert second_response.json()["status"] == "duplicate"

    async with get_session_factory()() as session:
        events = list((await session.execute(select(SourceEvent))).scalars().all())
        updates = list((await session.execute(select(PartnerUpdate))).scalars().all())
        assert len(events) == 1
        assert len(updates) == 1

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_jira_event_for_unmapped_issue_is_ignored() -> None:
    admin_email = f"jira-unmapped-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await configure_jira_integration(session, admin_email)

    response = await post_jira_payload(
        jira_event_payload(issue_key="AWS-999", issue_summary="Unmapped Jira issue")
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

    async with get_session_factory()() as session:
        assert list((await session.execute(select(SourceEvent))).scalars().all()) == []
        await cleanup_test_records(session, [], [admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_jira_webhook_rejects_invalid_signature() -> None:
    admin_email = f"jira-invalid-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await configure_jira_integration(session, admin_email)

    raw_body = json.dumps(jira_event_payload(issue_key="AWS-323")).encode()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/webhooks/jira/events",
            content=raw_body,
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 401

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await session.commit()


async def configure_jira_integration(session: AsyncSession, admin_email: str) -> None:
    repository = IdentityRepository(session)
    admin = repository.add_user_with_local_password(
        email=admin_email,
        display_name="Jira Admin",
        password_hash=hash_password("test-password"),
        roles=[RoleType.admin],
    )
    await session.commit()
    service = AdminIntegrationService(session, get_settings())
    await service.update_credentials(
        integration_type=IntegrationType.jira,
        payload=IntegrationCredentialUpdateRequest(
            secrets={
                "base_url": "https://jira.example.com",
                "service_token": "test-jira-token",
                "webhook_secret": JIRA_WEBHOOK_SECRET,
            }
        ),
        current_admin=user_to_response(admin),
    )
    await service.test_integration(
        integration_type=IntegrationType.jira,
        current_admin=user_to_response(admin),
    )


async def create_active_jira_source(
    session: AsyncSession,
    *,
    partner_name: str,
    contributor_email: str,
    issue_key: str,
) -> ConnectedSource:
    contributor = User(email=contributor_email, display_name="Jira Contributor")
    contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
    partner = Partner(
        name=partner_name,
        description="Jira partner",
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
            source_type="jira_issue",
            source_url=f"https://jira.example.com/browse/{issue_key}",
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


def jira_event_payload(
    *,
    issue_key: str,
    issue_summary: str = "Jira partner status update",
) -> dict:
    return {
        "webhookEvent": "jira:issue_updated",
        "timestamp": 1786132000000,
        "issue": {
            "id": "10001",
            "key": issue_key,
            "self": f"https://jira.example.com/rest/api/3/issue/{issue_key}",
            "fields": {
                "summary": issue_summary,
                "project": {"key": "AWS"},
                "issuetype": {"name": "Task"},
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "assignee": {"accountId": "jira-assignee-123"},
                "reporter": {"accountId": "jira-reporter-123"},
            },
        },
        "changelog": {
            "id": "20001",
            "items": [
                {
                    "field": "status",
                    "fromString": "To Do",
                    "toString": "In Progress",
                }
            ],
        },
    }


async def post_jira_payload(payload: dict) -> httpx.Response:
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="http://testserver",
    ) as client:
        return await client.post(
            "/api/webhooks/jira/events",
            content=raw_body,
            headers={
                "X-Hub-Signature-256": sign_jira_body(raw_body),
                "Content-Type": "application/json",
            },
        )


def sign_jira_body(raw_body: bytes) -> str:
    return "sha256=" + hmac.new(
        JIRA_WEBHOOK_SECRET.encode(),
        raw_body,
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
    await session.execute(delete(PartnerUpdate))
    await session.execute(delete(SourceEvent))
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
