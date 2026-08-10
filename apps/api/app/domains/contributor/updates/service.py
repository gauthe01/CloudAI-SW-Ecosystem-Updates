import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.domains.contributor.metadata.service import format_cycle_month, parse_cycle_month
from app.domains.contributor.updates.schemas import (
    ManualUpdateCreateRequest,
    PartnerUpdateCreatePayload,
    PartnerUpdateEditRequest,
    PartnerUpdateResponse,
)
from app.domains.contributor.updates.rich_text import sanitize_update_summary_html
from app.domains.identity.schemas import UserResponse


class ContributorUpdateService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_updates(
        self,
        *,
        partner_id: uuid.UUID,
        cycle: str,
        update_status: PartnerUpdateStatus,
        current_user: UserResponse,
        search: str | None = None,
    ) -> list[PartnerUpdateResponse]:
        cycle_month = parse_cycle_month(cycle)
        await self._ensure_assigned_active_partner(partner_id, current_user)
        statement = (
            select(PartnerUpdate)
            .where(PartnerUpdate.partner_id == partner_id)
            .where(PartnerUpdate.cycle_month == cycle_month)
            .where(PartnerUpdate.status == update_status.value)
            .order_by(PartnerUpdate.updated_at.desc(), PartnerUpdate.created_at.desc())
        )
        cleaned_search = search.strip() if search else ""
        if cleaned_search:
            query = f"%{cleaned_search.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(PartnerUpdate.title).like(query),
                    func.lower(PartnerUpdate.summary).like(query),
                    func.lower(PartnerUpdate.source_label).like(query),
                )
            )
        result = await self.db.execute(statement)
        return [self._to_response(update) for update in result.scalars().all()]

    async def create_pending_update(
        self,
        *,
        partner_id: uuid.UUID,
        cycle: str,
        payload: PartnerUpdateCreatePayload,
        current_user: UserResponse,
    ) -> PartnerUpdateResponse:
        cycle_month = parse_cycle_month(cycle)
        await self._ensure_assigned_active_partner(partner_id, current_user)
        now = datetime.now(UTC)
        update = PartnerUpdate(
            partner_id=partner_id,
            cycle_month=cycle_month,
            title=payload.title,
            summary=payload.summary,
            source_type=payload.source_type.value,
            source_label=clean_optional(payload.source_label),
            source_url=str(payload.source_url) if payload.source_url else None,
            source_event_key=clean_optional(payload.source_event_key),
            status=PartnerUpdateStatus.pending.value,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(update)
        await self.db.commit()
        return self._to_response(update)

    async def create_manual_update(
        self,
        *,
        partner_id: uuid.UUID,
        cycle: str,
        payload: ManualUpdateCreateRequest,
        current_user: UserResponse,
    ) -> PartnerUpdateResponse:
        return await self.create_pending_update(
            partner_id=partner_id,
            cycle=cycle,
            payload=PartnerUpdateCreatePayload(
                title=payload.title,
                summary=payload.summary,
            ),
            current_user=current_user,
        )

    async def edit_pending_update(
        self,
        *,
        partner_id: uuid.UUID,
        update_id: uuid.UUID,
        payload: PartnerUpdateEditRequest,
        current_user: UserResponse,
    ) -> PartnerUpdateResponse:
        await self._ensure_assigned_active_partner(partner_id, current_user)
        update = await self._get_partner_update_or_404(partner_id, update_id)
        self._ensure_pending(update)
        update.title = payload.title
        update.summary = payload.summary
        update.updated_at = datetime.now(UTC)
        await self.db.commit()
        return self._to_response(update)

    async def approve_update(
        self,
        *,
        partner_id: uuid.UUID,
        update_id: uuid.UUID,
        current_user: UserResponse,
    ) -> PartnerUpdateResponse:
        await self._ensure_assigned_active_partner(partner_id, current_user)
        update = await self._get_partner_update_or_404(partner_id, update_id)
        self._ensure_pending(update)
        now = datetime.now(UTC)
        update.status = PartnerUpdateStatus.approved.value
        update.approved_by = current_user.user_id
        update.approved_at = now
        update.updated_at = now
        await self.db.commit()
        return self._to_response(update)

    async def dismiss_update(
        self,
        *,
        partner_id: uuid.UUID,
        update_id: uuid.UUID,
        current_user: UserResponse,
    ) -> PartnerUpdateResponse:
        await self._ensure_assigned_active_partner(partner_id, current_user)
        update = await self._get_partner_update_or_404(partner_id, update_id)
        self._ensure_pending(update)
        now = datetime.now(UTC)
        update.status = PartnerUpdateStatus.rejected.value
        update.rejected_by = current_user.user_id
        update.rejected_at = now
        update.updated_at = now
        await self.db.commit()
        return self._to_response(update)

    async def _ensure_assigned_active_partner(
        self,
        partner_id: uuid.UUID,
        current_user: UserResponse,
    ) -> None:
        statement = (
            select(Partner.partner_id)
            .join(
                PartnerContributorAssignment,
                PartnerContributorAssignment.partner_id == Partner.partner_id,
            )
            .where(Partner.partner_id == partner_id)
            .where(PartnerContributorAssignment.user_id == current_user.user_id)
            .where(Partner.status == PartnerStatus.active.value)
        )
        result = await self.db.execute(statement)
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Partner updates are not assigned to this contributor.",
            )

    async def _get_partner_update_or_404(
        self,
        partner_id: uuid.UUID,
        update_id: uuid.UUID,
    ) -> PartnerUpdate:
        statement = select(PartnerUpdate).where(
            PartnerUpdate.partner_id == partner_id,
            PartnerUpdate.update_id == update_id,
        )
        result = await self.db.execute(statement)
        update = result.scalar_one_or_none()
        if update is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Update not found.",
            )
        return update

    def _ensure_pending(self, update: PartnerUpdate) -> None:
        if update.status != PartnerUpdateStatus.pending.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending updates can be changed.",
            )

    def _to_response(self, update: PartnerUpdate) -> PartnerUpdateResponse:
        return PartnerUpdateResponse(
            update_id=update.update_id,
            partner_id=update.partner_id,
            cycle=format_cycle_month(update.cycle_month),
            title=update.title,
            summary=sanitize_update_summary_html(update.summary),
            source_type=update.source_type,
            source_label=update.source_label,
            source_url=update.source_url,
            status=update.status,
            created_at=update.created_at,
            updated_at=update.updated_at,
            approved_at=update.approved_at,
            approved_by=update.approved_by,
            rejected_at=update.rejected_at,
            rejected_by=update.rejected_by,
        )


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
