import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    IntegrationStatus,
    IntegrationTestRun,
    IntegrationType,
)
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_metadata import PartnerResourceLink, ResourceLinkSourceKind
from app.db.session import get_session_factory
from app.domains.admin.connected_sources.schemas import AdminConnectedSourceReviewRequest
from app.domains.admin.connected_sources.service import AdminConnectedSourceApprovalService
from app.domains.contributor.connected_sources.schemas import ConnectedSourceRequest
from app.domains.contributor.connected_sources.service import ContributorConnectedSourceService
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.service import user_to_response


@pytest.mark.asyncio
async def test_admin_approves_source_only_after_enabled_integration_and_access_test() -> None:
    admin_email = f"approval-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"approval-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Approval Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        admin, contributor, partner = await create_approval_fixture(
            session,
            admin_email=admin_email,
            contributor_email=contributor_email,
            partner_name=partner_name,
        )
        contributor_service = ContributorConnectedSourceService(session)
        source = await contributor_service.create_source(
            partner_id=partner.partner_id,
            payload=ConnectedSourceRequest(
                source_type="jira_issue",
                source_url="https://jira.example.com/browse/AWS-1400",
            ),
            current_user=user_to_response(contributor),
        )
        approval_service = AdminConnectedSourceApprovalService(session)

        listed_sources = await approval_service.list_sources()
        listed_source = next(
            item
            for item in listed_sources
            if item.connected_source_id == source.connected_source_id
        )
        assert listed_source.review_bucket == "needs_review"
        assert listed_source.integration_available is False
        assert listed_source.partner.name == partner_name
        assert listed_source.requested_by.email == contributor_email

        with pytest.raises(HTTPException) as approve_exc:
            await approval_service.approve_source(
                connected_source_id=source.connected_source_id,
                current_admin=user_to_response(admin),
            )
        assert approve_exc.value.status_code == status.HTTP_409_CONFLICT

        needs_setup = await approval_service.test_access(source.connected_source_id)
        assert needs_setup.status == ConnectedSourceStatus.needs_access_setup
        assert needs_setup.review_bucket == "attention"
        assert "global integration must be enabled" in (needs_setup.access_test_summary or "")

        await enable_integration(session, IntegrationType.jira)
        retested = await approval_service.test_access(source.connected_source_id)
        assert retested.status == ConnectedSourceStatus.pending
        assert retested.integration_available is True
        assert retested.last_tested_at is not None

        approved = await approval_service.approve_source(
            connected_source_id=source.connected_source_id,
            current_admin=user_to_response(admin),
        )
        assert approved.status == ConnectedSourceStatus.active
        assert approved.review_bucket == "active"
        assert approved.approved_by is not None
        assert approved.approved_by.email == admin_email
        resource_result = await session.execute(
            select(PartnerResourceLink).where(
                PartnerResourceLink.partner_id == partner.partner_id,
                PartnerResourceLink.source_kind == ResourceLinkSourceKind.connected_source.value,
                PartnerResourceLink.url == "https://jira.example.com/browse/AWS-1400",
            )
        )
        resource_link = resource_result.scalar_one()
        assert resource_link.title == "AWS-1400"
        assert resource_link.archived_at is None

        contributor_sources = await contributor_service.list_sources(
            partner_id=partner.partner_id,
            current_user=user_to_response(contributor),
        )
        assert contributor_sources[0].status == ConnectedSourceStatus.active

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_admin_can_reject_needs_access_and_disable_sources() -> None:
    admin_email = f"approval-state-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"approval-state-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Approval State Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        admin, contributor, partner = await create_approval_fixture(
            session,
            admin_email=admin_email,
            contributor_email=contributor_email,
            partner_name=partner_name,
        )
        contributor_service = ContributorConnectedSourceService(session)
        slack_source = await contributor_service.create_source(
            partner_id=partner.partner_id,
            payload=ConnectedSourceRequest(
                source_type="slack_channel",
                channel_name="#aws-approvals",
                channel_id="CAPPROVALS01",
                bot_invited_confirmed=True,
            ),
            current_user=user_to_response(contributor),
        )
        approval_service = AdminConnectedSourceApprovalService(session)

        needs_access = await approval_service.mark_needs_access_setup(
            connected_source_id=slack_source.connected_source_id,
            payload=AdminConnectedSourceReviewRequest(note="Invite bot again."),
        )
        assert needs_access.status == ConnectedSourceStatus.needs_access_setup
        assert needs_access.review_bucket == "attention"

        rejected = await approval_service.reject_source(
            connected_source_id=slack_source.connected_source_id,
            payload=AdminConnectedSourceReviewRequest(note="Duplicate channel request."),
        )
        assert rejected.status == ConnectedSourceStatus.rejected
        assert rejected.review_bucket == "rejected"
        assert rejected.access_test_summary == "Duplicate channel request."

        jira_source = await contributor_service.create_source(
            partner_id=partner.partner_id,
            payload=ConnectedSourceRequest(
                source_type="jira_issue",
                source_url="https://jira.example.com/browse/AWS-1401",
            ),
            current_user=user_to_response(contributor),
        )
        await enable_integration(session, IntegrationType.jira)
        await approval_service.test_access(jira_source.connected_source_id)
        approved = await approval_service.approve_source(
            connected_source_id=jira_source.connected_source_id,
            current_admin=user_to_response(admin),
        )
        assert approved.status == ConnectedSourceStatus.active

        disabled = await approval_service.disable_source(
            connected_source_id=jira_source.connected_source_id,
            payload=AdminConnectedSourceReviewRequest(note="Temporary access issue."),
        )
        assert disabled.status == ConnectedSourceStatus.disabled
        assert disabled.review_bucket == "attention"
        assert disabled.access_test_summary == "Temporary access issue."
        archived_resource_result = await session.execute(
            select(PartnerResourceLink).where(
                PartnerResourceLink.partner_id == partner.partner_id,
                PartnerResourceLink.source_kind == ResourceLinkSourceKind.connected_source.value,
                PartnerResourceLink.url == "https://jira.example.com/browse/AWS-1401",
            )
        )
        archived_resource_link = archived_resource_result.scalar_one()
        assert archived_resource_link.archived_at is not None

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


async def create_approval_fixture(
    session: AsyncSession,
    *,
    admin_email: str,
    contributor_email: str,
    partner_name: str,
) -> tuple[User, User, Partner]:
    repository = IdentityRepository(session)
    admin = repository.add_user_with_local_password(
        email=admin_email,
        display_name="Approval Admin",
        password_hash=hash_password("test-password"),
        roles=[RoleType.admin],
    )
    contributor = repository.add_user(
        email=contributor_email,
        display_name="Approval Contributor",
        roles=[RoleType.contributor],
    )
    partner = Partner(
        name=partner_name,
        description="Approval partner",
        status=PartnerStatus.active.value,
    )
    session.add(partner)
    await session.flush()
    session.add(
        PartnerContributorAssignment(
            partner_id=partner.partner_id,
            user_id=contributor.user_id,
            assigned_by=admin.user_id,
        )
    )
    await session.commit()
    return admin, contributor, partner


async def enable_integration(session: AsyncSession, integration_type: IntegrationType) -> None:
    now = datetime.now(UTC)
    result = await session.execute(
        select(Integration).where(Integration.integration_type == integration_type.value)
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        integration = Integration(
            integration_type=integration_type.value,
            status=IntegrationStatus.enabled.value,
            enabled_at=now,
            last_tested_at=now,
            last_test_status="succeeded",
            created_at=now,
            updated_at=now,
        )
        session.add(integration)
    else:
        integration.status = IntegrationStatus.enabled.value
        integration.enabled_at = now
        integration.last_tested_at = now
        integration.last_test_status = "succeeded"
        integration.updated_at = now
    await session.commit()


async def cleanup_test_records(
    session: AsyncSession,
    partner_names: list[str],
    emails: list[str],
) -> None:
    partner_ids = select_partner_ids(partner_names)
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
