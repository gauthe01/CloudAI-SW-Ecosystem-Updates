import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.connected_source import (
    ConnectedSource,
    ConnectedSourceStatus,
)
from app.db.models.identity import RoleType, User, UserRoleAssignment, UserSession
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.session import get_session_factory
from app.domains.contributor.connected_sources.schemas import ConnectedSourceRequest
from app.domains.contributor.connected_sources.service import ContributorConnectedSourceService
from app.domains.contributor.partners.service import ContributorPartnerService
from app.domains.identity.service import user_to_response


@pytest.mark.asyncio
async def test_contributor_connected_source_lifecycle_and_counts() -> None:
    contributor_email = f"source-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Source Partner {uuid.uuid4()}"
    unassigned_partner_name = f"Unassigned Source Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(
            session,
            [partner_name, unassigned_partner_name],
            [contributor_email],
        )
        contributor = User(email=contributor_email, display_name="Source Contributor")
        contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
        partner = Partner(
            name=partner_name,
            description="Source partner",
            status=PartnerStatus.active.value,
        )
        unassigned_partner = Partner(
            name=unassigned_partner_name,
            description="Unassigned source partner",
            status=PartnerStatus.active.value,
        )
        session.add_all([contributor, partner, unassigned_partner])
        await session.flush()
        session.add(
            PartnerContributorAssignment(
                partner_id=partner.partner_id,
                user_id=contributor.user_id,
            )
        )
        await session.commit()

        current_user = user_to_response(contributor)
        service = ContributorConnectedSourceService(session)
        jira_source = await service.create_source(
            partner_id=partner.partner_id,
            payload=ConnectedSourceRequest(
                source_type="jira_issue",
                source_url="https://jira.example.com/browse/AWS-123",
            ),
            current_user=current_user,
        )
        assert jira_source.status == ConnectedSourceStatus.pending
        assert jira_source.contributor_status == "pending"
        assert jira_source.external_identifier == "AWS-123"
        assert jira_source.details.issue_key == "AWS-123"

        slack_source = await service.create_source(
            partner_id=partner.partner_id,
            payload=ConnectedSourceRequest(
                source_type="slack_channel",
                channel_name="#aws-partner",
                channel_id="C0123456789",
                bot_invited_confirmed=True,
            ),
            current_user=current_user,
        )
        assert slack_source.details.channel_id == "C0123456789"

        listed_sources = await service.list_sources(
            partner_id=partner.partner_id,
            current_user=current_user,
        )
        assert {source.connected_source_id for source in listed_sources} == {
            jira_source.connected_source_id,
            slack_source.connected_source_id,
        }

        with pytest.raises(HTTPException) as duplicate_exc:
            await service.create_source(
                partner_id=partner.partner_id,
                payload=ConnectedSourceRequest(
                    source_type="jira_issue",
                    source_url="https://jira.example.com/browse/AWS-123",
                ),
                current_user=current_user,
            )
        assert duplicate_exc.value.status_code == 409

        with pytest.raises(HTTPException) as assignment_exc:
            await service.create_source(
                partner_id=unassigned_partner.partner_id,
                payload=ConnectedSourceRequest(
                    source_type="jira_issue",
                    source_url="https://jira.example.com/browse/AWS-456",
                ),
                current_user=current_user,
            )
        assert assignment_exc.value.status_code == 403

        github_source = await service.update_source(
            partner_id=partner.partner_id,
            connected_source_id=jira_source.connected_source_id,
            payload=ConnectedSourceRequest(
                source_type="github_issue",
                source_url="https://github.com/arm/example/issues/42",
            ),
            current_user=current_user,
        )
        assert github_source.source_type == "github_issue"
        assert github_source.details.github_repository == "arm/example"
        assert github_source.details.github_number == 42

        archived_source = await service.archive_source(
            partner_id=partner.partner_id,
            connected_source_id=slack_source.connected_source_id,
            current_user=current_user,
        )
        assert archived_source.status == ConnectedSourceStatus.archived

        active_source = await set_source_status(
            session,
            github_source.connected_source_id,
            ConnectedSourceStatus.active,
        )
        paused_source = await service.pause_source(
            partner_id=partner.partner_id,
            connected_source_id=active_source.connected_source_id,
            current_user=current_user,
        )
        assert paused_source.status == ConnectedSourceStatus.disabled
        resumed_source = await service.resume_source(
            partner_id=partner.partner_id,
            connected_source_id=active_source.connected_source_id,
            current_user=current_user,
        )
        assert resumed_source.status == ConnectedSourceStatus.active

        partner_service = ContributorPartnerService(session)
        context = await partner_service.get_dashboard_context(
            partner_id=partner.partner_id,
            current_user=current_user,
        )
        assert context.tab_counts.connected_sources == 1
        assert context.partner.connected_sources_count == 1

        await cleanup_test_records(
            session,
            [partner_name, unassigned_partner_name],
            [contributor_email],
        )
        await session.commit()


async def set_source_status(
    session: AsyncSession,
    connected_source_id: uuid.UUID,
    status: ConnectedSourceStatus,
) -> ConnectedSource:
    result = await session.execute(
        select(ConnectedSource).where(ConnectedSource.connected_source_id == connected_source_id)
    )
    source = result.scalar_one()
    source.status = status.value
    await session.commit()
    return source


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
