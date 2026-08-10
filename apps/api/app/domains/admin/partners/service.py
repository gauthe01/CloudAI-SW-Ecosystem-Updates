import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.identity import RoleType, User, UserStatus
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.domains.admin.partners.schemas import (
    AdminPartnerCreateRequest,
    AdminPartnerResponse,
    AdminPartnerUpdateRequest,
    AssignedContributorResponse,
)
from app.domains.identity.schemas import UserResponse


class AdminPartnerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_partners(self) -> list[AdminPartnerResponse]:
        partners = await self._load_partners()
        return [await self._partner_to_response(partner) for partner in partners]

    async def create_partner(
        self,
        *,
        payload: AdminPartnerCreateRequest,
        current_admin: UserResponse,
    ) -> AdminPartnerResponse:
        await self._ensure_partner_name_available(payload.name)
        contributors = await self._validate_contributors(payload.assigned_contributor_user_ids)

        partner = Partner(
            name=payload.name,
            description=_clean_optional(payload.description),
            status=PartnerStatus.active.value,
        )
        self.db.add(partner)
        await self.db.flush()
        await self._replace_assignments(
            partner=partner,
            contributors=contributors,
            assigned_by=current_admin.user_id,
        )
        await self.db.commit()
        return await self._partner_to_response(partner)

    async def update_partner(
        self,
        *,
        partner_id: uuid.UUID,
        payload: AdminPartnerUpdateRequest,
        current_admin: UserResponse,
    ) -> AdminPartnerResponse:
        partner = await self._get_partner_or_404(partner_id)

        if payload.name is not None and payload.name != partner.name:
            await self._ensure_partner_name_available(payload.name, exclude_partner_id=partner_id)
            partner.name = payload.name

        if "description" in payload.model_fields_set:
            partner.description = _clean_optional(payload.description)

        if payload.assigned_contributor_user_ids is not None:
            contributors = await self._validate_contributors(payload.assigned_contributor_user_ids)
            await self._replace_assignments(
                partner=partner,
                contributors=contributors,
                assigned_by=current_admin.user_id,
            )

        partner.updated_at = datetime.now(UTC)
        await self.db.commit()
        return await self._partner_to_response(partner)

    async def archive_partner(self, partner_id: uuid.UUID) -> AdminPartnerResponse:
        partner = await self._get_partner_or_404(partner_id)
        now = datetime.now(UTC)
        partner.status = PartnerStatus.archived.value
        partner.archived_at = now
        partner.updated_at = now
        await self.db.commit()
        return await self._partner_to_response(partner)

    async def restore_partner(self, partner_id: uuid.UUID) -> AdminPartnerResponse:
        partner = await self._get_partner_or_404(partner_id)
        partner.status = PartnerStatus.active.value
        partner.archived_at = None
        partner.updated_at = datetime.now(UTC)
        await self.db.commit()
        return await self._partner_to_response(partner)

    async def _load_partners(self) -> list[Partner]:
        statement = (
            select(Partner)
            .options(selectinload(Partner.contributor_assignments))
            .order_by(Partner.name.asc())
        )
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def _get_partner_or_404(self, partner_id: uuid.UUID) -> Partner:
        statement = (
            select(Partner)
            .options(selectinload(Partner.contributor_assignments))
            .where(Partner.partner_id == partner_id)
        )
        result = await self.db.execute(statement)
        partner = result.scalar_one_or_none()
        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partner not found.",
            )
        return partner

    async def _ensure_partner_name_available(
        self,
        name: str,
        exclude_partner_id: uuid.UUID | None = None,
    ) -> None:
        statement = select(Partner).where(Partner.name == name)
        if exclude_partner_id is not None:
            statement = statement.where(Partner.partner_id != exclude_partner_id)
        result = await self.db.execute(statement)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A partner with this name already exists.",
            )

    async def _validate_contributors(self, user_ids: list[uuid.UUID]) -> list[User]:
        unique_user_ids = list(dict.fromkeys(user_ids))
        if not unique_user_ids:
            return []

        statement = (
            select(User)
            .options(selectinload(User.role_assignments))
            .where(User.user_id.in_(unique_user_ids))
        )
        result = await self.db.execute(statement)
        users = list(result.scalars().all())
        found_ids = {user.user_id for user in users}
        missing_ids = [user_id for user_id in unique_user_ids if user_id not in found_ids]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more assigned contributors do not exist.",
            )

        invalid_users = [
            user
            for user in users
            if user.status != UserStatus.active.value
            or RoleType.contributor
            not in {assignment.role_type for assignment in user.role_assignments}
        ]
        if invalid_users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned users must be active contributors.",
            )

        return sorted(users, key=lambda user: user.display_name)

    async def _replace_assignments(
        self,
        *,
        partner: Partner,
        contributors: list[User],
        assigned_by: uuid.UUID,
    ) -> None:
        await self.db.execute(
            delete(PartnerContributorAssignment).where(
                PartnerContributorAssignment.partner_id == partner.partner_id
            )
        )
        self.db.add_all(
            [
                PartnerContributorAssignment(
                    partner_id=partner.partner_id,
                    user_id=user.user_id,
                    assigned_by=assigned_by,
                )
                for user in contributors
            ]
        )

    async def _partner_to_response(self, partner: Partner) -> AdminPartnerResponse:
        contributors = await self._load_assigned_contributors(partner)
        return AdminPartnerResponse(
            partner_id=partner.partner_id,
            name=partner.name,
            description=partner.description,
            status=PartnerStatus(partner.status),
            assigned_contributors=[
                AssignedContributorResponse(
                    user_id=user.user_id,
                    email=user.email,
                    display_name=user.display_name,
                )
                for user in contributors
            ],
            created_at=partner.created_at,
            updated_at=partner.updated_at,
            archived_at=partner.archived_at,
        )

    async def _load_assigned_contributors(self, partner: Partner) -> list[User]:
        statement = (
            select(User)
            .join(
                PartnerContributorAssignment,
                PartnerContributorAssignment.user_id == User.user_id,
            )
            .where(PartnerContributorAssignment.partner_id == partner.partner_id)
            .order_by(User.display_name.asc())
        )
        result = await self.db.execute(statement)
        return list(result.scalars().all())


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
