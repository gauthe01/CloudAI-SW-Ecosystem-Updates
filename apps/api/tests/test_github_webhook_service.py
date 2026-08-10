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
from app.domains.webhooks.github.security import verify_github_signature
from app.main import create_app

GITHUB_WEBHOOK_SECRET = "test-github-webhook-secret"


def test_verify_github_signature_accepts_valid_signature_and_rejects_invalid() -> None:
    raw_body = b'{"action":"opened"}'
    signature = sign_github_body(raw_body)

    assert verify_github_signature(
        webhook_secret=GITHUB_WEBHOOK_SECRET,
        raw_body=raw_body,
        signature=signature,
    )
    assert not verify_github_signature(
        webhook_secret=GITHUB_WEBHOOK_SECRET,
        raw_body=raw_body,
        signature="sha256=invalid",
    )


@pytest.mark.asyncio
async def test_github_issue_event_creates_pending_update_without_raw_storage() -> None:
    admin_email = f"github-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"github-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"GitHub Partner {uuid.uuid4()}"
    repository = "arm/example"
    issue_number = 42
    issue_title = "Release decision risk for AWS validation"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_github_integration(session, admin_email)
        await create_active_github_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            source_type="github_issue",
            source_url=f"https://github.com/{repository}/issues/{issue_number}",
        )

    payload = github_issue_payload(
        repository=repository,
        issue_number=issue_number,
        issue_title=issue_title,
    )
    response = await post_github_payload(payload, event_name="issues", delivery_id="delivery-1")

    assert response.status_code == 200
    assert response.json()["processed_count"] == 1

    async with get_session_factory()() as session:
        source_events = list((await session.execute(select(SourceEvent))).scalars().all())
        payloads = list((await session.execute(select(SourcePayload))).scalars().all())
        updates = list((await session.execute(select(PartnerUpdate))).scalars().all())

        assert len(source_events) == 1
        assert source_events[0].source_type == "github_issue"
        assert source_events[0].technical_metadata["event_type"] == "issues"
        assert source_events[0].technical_metadata["repository"] == repository
        assert issue_title not in json.dumps(source_events[0].technical_metadata)

        assert len(payloads) == 1
        assert payloads[0].raw_payload_json is None
        assert payloads[0].raw_text_encrypted is None

        assert len(updates) == 1
        assert updates[0].status == PartnerUpdateStatus.pending.value
        assert updates[0].source_type == "github"
        assert updates[0].source_label == f"{repository} Issue #{issue_number}"
        assert updates[0].source_url == f"https://github.com/{repository}/issues/{issue_number}"
        assert updates[0].source_event_id == source_events[0].source_event_id
        assert issue_title in updates[0].summary

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_github_repository_source_processes_push_event() -> None:
    admin_email = f"github-repo-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"github-repo-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"GitHub Repo Partner {uuid.uuid4()}"
    repository = "arm/repo-example"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_github_integration(session, admin_email)
        await create_active_github_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            source_type="github_repository",
            source_url=f"https://github.com/{repository}",
        )

    response = await post_github_payload(
        github_push_payload(repository=repository),
        event_name="push",
        delivery_id="delivery-push-1",
    )

    assert response.status_code == 200
    assert response.json()["processed_count"] == 1

    async with get_session_factory()() as session:
        updates = list((await session.execute(select(PartnerUpdate))).scalars().all())
        assert len(updates) == 1
        assert updates[0].source_label == repository
        assert "commit" in updates[0].summary

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_github_duplicate_delivery_does_not_duplicate_pending_update() -> None:
    admin_email = f"github-duplicate-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"github-duplicate-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"GitHub Duplicate Partner {uuid.uuid4()}"
    repository = "arm/duplicate"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_github_integration(session, admin_email)
        await create_active_github_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            source_type="github_issue",
            source_url=f"https://github.com/{repository}/issues/7",
        )

    payload = github_issue_payload(repository=repository, issue_number=7)
    first_response = await post_github_payload(
        payload,
        event_name="issues",
        delivery_id="same-delivery",
    )
    second_response = await post_github_payload(
        payload,
        event_name="issues",
        delivery_id="same-delivery",
    )

    assert first_response.json()["processed_count"] == 1
    assert second_response.json()["duplicate_count"] == 1

    async with get_session_factory()() as session:
        events = list((await session.execute(select(SourceEvent))).scalars().all())
        updates = list((await session.execute(select(PartnerUpdate))).scalars().all())
        assert len(events) == 1
        assert len(updates) == 1

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_github_event_for_unmapped_scope_is_ignored() -> None:
    admin_email = f"github-unmapped-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await configure_github_integration(session, admin_email)

    response = await post_github_payload(
        github_issue_payload(repository="arm/unmapped", issue_number=999),
        event_name="issues",
        delivery_id="unmapped-delivery",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

    async with get_session_factory()() as session:
        assert list((await session.execute(select(SourceEvent))).scalars().all()) == []
        await cleanup_test_records(session, [], [admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_github_webhook_rejects_invalid_signature() -> None:
    admin_email = f"github-invalid-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await configure_github_integration(session, admin_email)

    raw_body = json.dumps(github_issue_payload(), separators=(",", ":")).encode()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/webhooks/github/events",
            content=raw_body,
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "issues",
                "X-GitHub-Delivery": "invalid-delivery",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 401

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await session.commit()


async def configure_github_integration(session: AsyncSession, admin_email: str) -> None:
    repository = IdentityRepository(session)
    admin = repository.add_user_with_local_password(
        email=admin_email,
        display_name="GitHub Admin",
        password_hash=hash_password("test-password"),
        roles=[RoleType.admin],
    )
    await session.commit()
    service = AdminIntegrationService(session, get_settings())
    await service.update_credentials(
        integration_type=IntegrationType.github,
        payload=IntegrationCredentialUpdateRequest(
            secrets={
                "app_id": "12345",
                "private_key": "test-private-key",
                "webhook_secret": GITHUB_WEBHOOK_SECRET,
            }
        ),
        current_admin=user_to_response(admin),
    )
    await service.test_integration(
        integration_type=IntegrationType.github,
        current_admin=user_to_response(admin),
    )


async def create_active_github_source(
    session: AsyncSession,
    *,
    partner_name: str,
    contributor_email: str,
    source_type: str,
    source_url: str,
) -> ConnectedSource:
    contributor = User(email=contributor_email, display_name="GitHub Contributor")
    contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
    partner = Partner(
        name=partner_name,
        description="GitHub partner",
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
            source_type=source_type,
            source_url=source_url,
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


def github_issue_payload(
    *,
    repository: str = "arm/example",
    issue_number: int = 42,
    issue_title: str = "GitHub issue identifies a release risk",
) -> dict:
    owner, repo = repository.split("/", 1)
    return {
        "action": "opened",
        "repository": {
            "full_name": repository,
            "name": repo,
            "html_url": f"https://github.com/{repository}",
            "owner": {"login": owner},
        },
        "issue": {
            "number": issue_number,
            "title": issue_title,
            "body": "The partner validation is blocked until the release decision is made.",
            "html_url": f"https://github.com/{repository}/issues/{issue_number}",
            "updated_at": "2026-08-07T20:15:00Z",
        },
        "sender": {"login": "octocat"},
    }


def github_push_payload(*, repository: str) -> dict:
    owner, repo = repository.split("/", 1)
    return {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": repository,
            "name": repo,
            "html_url": f"https://github.com/{repository}",
            "owner": {"login": owner},
        },
        "head_commit": {
            "id": "abc123",
            "message": "Update partner release status",
            "timestamp": "2026-08-07T20:20:00Z",
        },
        "commits": [{"id": "abc123"}],
        "sender": {"login": "octocat"},
    }


async def post_github_payload(
    payload: dict,
    *,
    event_name: str,
    delivery_id: str,
) -> httpx.Response:
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="http://testserver",
    ) as client:
        return await client.post(
            "/api/webhooks/github/events",
            content=raw_body,
            headers={
                "X-Hub-Signature-256": sign_github_body(raw_body),
                "X-GitHub-Event": event_name,
                "X-GitHub-Delivery": delivery_id,
                "Content-Type": "application/json",
            },
        )


def sign_github_body(raw_body: bytes) -> str:
    return "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
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
