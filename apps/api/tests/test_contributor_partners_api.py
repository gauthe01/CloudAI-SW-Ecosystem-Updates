import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import (
    RoleType,
    User,
    UserRoleAssignment,
    UserSession,
)
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.db.session import get_session_factory
from app.domains.contributor.partners.service import ContributorPartnerService
from app.domains.identity.service import user_to_response


@pytest.mark.asyncio
async def test_contributor_partners_returns_only_active_assigned_partners() -> None:
    contributor_email = f"assigned-partner-{uuid.uuid4()}@example.com"
    active_partner_name = f"Active Partner {uuid.uuid4()}"
    archived_partner_name = f"Archived Partner {uuid.uuid4()}"
    unassigned_partner_name = f"Unassigned Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(
            session,
            [active_partner_name, archived_partner_name, unassigned_partner_name],
            [contributor_email],
        )
        contributor = User(email=contributor_email, display_name="Assigned Contributor")
        contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
        active_partner = Partner(
            name=active_partner_name,
            description="Visible partner",
            status=PartnerStatus.active.value,
        )
        archived_partner = Partner(
            name=archived_partner_name,
            description="Hidden partner",
            status=PartnerStatus.archived.value,
        )
        unassigned_partner = Partner(
            name=unassigned_partner_name,
            description="Denied partner",
            status=PartnerStatus.active.value,
        )
        session.add_all([contributor, active_partner, archived_partner, unassigned_partner])
        await session.flush()
        session.add_all(
            [
                PartnerContributorAssignment(
                    partner_id=active_partner.partner_id,
                    user_id=contributor.user_id,
                ),
                PartnerContributorAssignment(
                    partner_id=archived_partner.partner_id,
                    user_id=contributor.user_id,
                ),
            ]
        )
        await session.commit()

        service = ContributorPartnerService(session)
        partners = await service.list_assigned_partners(user_to_response(contributor))

        assert [partner.name for partner in partners] == [active_partner_name]
        assert partners[0].updates_count == 0
        assert partners[0].connected_sources_count == 0
        assert partners[0].last_activity_at is None

        context = await service.get_dashboard_context(
            partner_id=active_partner.partner_id,
            current_user=user_to_response(contributor),
        )
        assert context.partner.name == active_partner_name
        assert context.default_tab == "pending_updates"
        assert context.tab_counts.pending_updates == 0
        assert context.tab_counts.approved_updates == 0
        assert context.tab_counts.connected_sources == 0

        with pytest.raises(HTTPException) as exc_info:
            await service.get_dashboard_context(
                partner_id=unassigned_partner.partner_id,
                current_user=user_to_response(contributor),
            )
        assert exc_info.value.status_code == 403

        await cleanup_test_records(
            session,
            [active_partner_name, archived_partner_name, unassigned_partner_name],
            [contributor_email],
        )
        await session.commit()


@pytest.mark.asyncio
async def test_dashboard_context_counts_are_scoped_to_selected_cycle() -> None:
    contributor_email = f"cycle-counts-{uuid.uuid4()}@example.com"
    partner_name = f"Cycle Counts Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [contributor_email])
        contributor = User(email=contributor_email, display_name="Cycle Counts Contributor")
        contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
        partner = Partner(
            name=partner_name,
            description="Cycle-scoped dashboard counts",
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
        session.add_all(
            [
                PartnerUpdate(
                    partner_id=partner.partner_id,
                    cycle_month=date(2026, 7, 1),
                    title="July pending one",
                    summary="Pending update for July.",
                    status=PartnerUpdateStatus.pending.value,
                ),
                PartnerUpdate(
                    partner_id=partner.partner_id,
                    cycle_month=date(2026, 7, 1),
                    title="July pending two",
                    summary="Another pending update for July.",
                    status=PartnerUpdateStatus.pending.value,
                ),
                PartnerUpdate(
                    partner_id=partner.partner_id,
                    cycle_month=date(2026, 8, 1),
                    title="August approved",
                    summary="Approved update for August.",
                    status=PartnerUpdateStatus.approved.value,
                ),
            ]
        )
        await session.commit()

        service = ContributorPartnerService(session)
        current_user = user_to_response(contributor)
        july_context = await service.get_dashboard_context(
            partner_id=partner.partner_id,
            current_user=current_user,
            cycle="2026-07",
        )
        august_context = await service.get_dashboard_context(
            partner_id=partner.partner_id,
            current_user=current_user,
            cycle="2026-08",
        )

        assert july_context.active_cycle == "2026-07"
        assert july_context.active_cycle_label == "July 2026"
        assert july_context.tab_counts.pending_updates == 2
        assert july_context.tab_counts.approved_updates == 0
        assert august_context.active_cycle == "2026-08"
        assert august_context.active_cycle_label == "August 2026"
        assert august_context.tab_counts.pending_updates == 0
        assert august_context.tab_counts.approved_updates == 1

        await cleanup_test_records(session, [partner_name], [contributor_email])
        await session.commit()


async def cleanup_test_records(
    session: AsyncSession,
    partner_names: list[str],
    emails: list[str],
) -> None:
    await session.execute(
        delete(PartnerUpdate).where(
            PartnerUpdate.partner_id.in_(select_partner_ids(partner_names))
        )
    )
    await session.execute(
        delete(PartnerContributorAssignment).where(
            PartnerContributorAssignment.partner_id.in_(select_partner_ids(partner_names))
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
