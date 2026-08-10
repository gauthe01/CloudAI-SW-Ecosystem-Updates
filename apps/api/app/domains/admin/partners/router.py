import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.admin.partners.schemas import (
    AdminPartnerCreateRequest,
    AdminPartnerListResponse,
    AdminPartnerResponse,
    AdminPartnerUpdateRequest,
)
from app.domains.admin.partners.service import AdminPartnerService
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse

router = APIRouter(prefix="/api/admin/partners", tags=["admin-partners"])


def get_admin_partner_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminPartnerService:
    return AdminPartnerService(db)


@router.get("", response_model=AdminPartnerListResponse)
async def list_partners(
    service: Annotated[AdminPartnerService, Depends(get_admin_partner_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminPartnerListResponse:
    return AdminPartnerListResponse(partners=await service.list_partners())


@router.post("", response_model=AdminPartnerResponse, status_code=status.HTTP_201_CREATED)
async def create_partner(
    payload: AdminPartnerCreateRequest,
    service: Annotated[AdminPartnerService, Depends(get_admin_partner_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminPartnerResponse:
    return await service.create_partner(payload=payload, current_admin=current_admin)


@router.patch("/{partner_id}", response_model=AdminPartnerResponse)
async def update_partner(
    partner_id: uuid.UUID,
    payload: AdminPartnerUpdateRequest,
    service: Annotated[AdminPartnerService, Depends(get_admin_partner_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminPartnerResponse:
    return await service.update_partner(
        partner_id=partner_id,
        payload=payload,
        current_admin=current_admin,
    )


@router.post("/{partner_id}/archive", response_model=AdminPartnerResponse)
async def archive_partner(
    partner_id: uuid.UUID,
    service: Annotated[AdminPartnerService, Depends(get_admin_partner_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminPartnerResponse:
    return await service.archive_partner(partner_id)


@router.post("/{partner_id}/restore", response_model=AdminPartnerResponse)
async def restore_partner(
    partner_id: uuid.UUID,
    service: Annotated[AdminPartnerService, Depends(get_admin_partner_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminPartnerResponse:
    return await service.restore_partner(partner_id)
