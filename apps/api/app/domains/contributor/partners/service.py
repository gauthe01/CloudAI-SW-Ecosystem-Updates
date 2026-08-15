import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.connected_source import ConnectedSource, ConnectedSourceStatus
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.domains.contributor.metadata.service import parse_cycle_month
from app.domains.contributor.partners.schemas import (
    ContributorDashboardContextResponse,
    ContributorDashboardTabCounts,
    ContributorPartnerResponse,
)
from app.domains.identity.schemas import UserResponse


class ContributorPartnerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_assigned_partners(
        self,
        current_user: UserResponse,
    ) -> list[ContributorPartnerResponse]:
        statement = (
            select(Partner)
            .join(
                PartnerContributorAssignment,
                PartnerContributorAssignment.partner_id == Partner.partner_id,
            )
            .where(PartnerContributorAssignment.user_id == current_user.user_id)
            .where(Partner.status == PartnerStatus.active.value)
            .order_by(Partner.name.asc())
        )
        result = await self.db.execute(statement)
        return [
            await self._partner_to_response(partner)
            for partner in result.scalars().all()
        ]

    async def get_dashboard_context(
        self,
        *,
        partner_id: uuid.UUID,
        current_user: UserResponse,
        cycle: str | None = None,
    ) -> ContributorDashboardContextResponse:
        partner = await self._get_assigned_active_partner(partner_id, current_user)
        active_cycle = datetime.now(UTC)
        cycle_month = parse_cycle_month(cycle) if cycle else active_cycle.replace(day=1).date()
        pending_count = await self._count_updates(
            partner_id=partner_id,
            status=PartnerUpdateStatus.pending,
            cycle_month=cycle_month,
        )
        approved_count = await self._count_updates(
            partner_id=partner_id,
            status=PartnerUpdateStatus.approved,
            cycle_month=cycle_month,
        )
        return ContributorDashboardContextResponse(
            partner=await self._partner_to_response(partner),
            active_cycle=cycle_month.strftime("%Y-%m"),
            active_cycle_label=cycle_month.strftime("%B %Y"),
            default_tab="pending_updates",
            tab_counts=ContributorDashboardTabCounts(
                pending_updates=pending_count,
                approved_updates=approved_count,
                connected_sources=await self._count_connected_sources(partner_id),
            ),
        )

    async def _get_assigned_active_partner(
        self,
        partner_id: uuid.UUID,
        current_user: UserResponse,
    ) -> Partner:
        statement = (
            select(Partner)
            .join(
                PartnerContributorAssignment,
                PartnerContributorAssignment.partner_id == Partner.partner_id,
            )
            .where(Partner.partner_id == partner_id)
            .where(PartnerContributorAssignment.user_id == current_user.user_id)
            .where(Partner.status == PartnerStatus.active.value)
        )
        result = await self.db.execute(statement)
        partner = result.scalar_one_or_none()
        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Partner workspace is not assigned to this contributor.",
            )
        return partner

    async def _partner_to_response(self, partner: Partner) -> ContributorPartnerResponse:
        updates_count = await self._count_active_updates(partner.partner_id)
        connected_sources_count = await self._count_connected_sources(partner.partner_id)
        last_activity_at = await self._get_last_update_activity(partner.partner_id)
        return ContributorPartnerResponse(
            partner_id=partner.partner_id,
            name=partner.name,
            description=partner.description,
            updates_count=updates_count,
            connected_sources_count=connected_sources_count,
            last_activity_at=last_activity_at,
        )

    async def _count_active_updates(self, partner_id: uuid.UUID) -> int:
        statement = (
            select(func.count())
            .select_from(PartnerUpdate)
            .where(PartnerUpdate.partner_id == partner_id)
            .where(
                PartnerUpdate.status.in_(
                    [PartnerUpdateStatus.pending.value, PartnerUpdateStatus.approved.value]
                )
            )
        )
        result = await self.db.execute(statement)
        return int(result.scalar_one())

    async def _count_updates(
        self,
        *,
        partner_id: uuid.UUID,
        status: PartnerUpdateStatus,
        cycle_month,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(PartnerUpdate)
            .where(PartnerUpdate.partner_id == partner_id)
            .where(PartnerUpdate.cycle_month == cycle_month)
            .where(PartnerUpdate.status == status.value)
        )
        result = await self.db.execute(statement)
        return int(result.scalar_one())

    async def _get_last_update_activity(self, partner_id: uuid.UUID):
        statement = select(func.max(PartnerUpdate.updated_at)).where(
            PartnerUpdate.partner_id == partner_id
        )
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def _count_connected_sources(self, partner_id: uuid.UUID) -> int:
        statement = (
            select(func.count())
            .select_from(ConnectedSource)
            .where(ConnectedSource.partner_id == partner_id)
            .where(ConnectedSource.status != ConnectedSourceStatus.archived.value)
        )
        result = await self.db.execute(statement)
        return int(result.scalar_one())
