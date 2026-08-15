import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType
from app.db.models.partner_update import PartnerUpdateStatus
from app.db.session import get_db_session
from app.domains.contributor.updates.schemas import (
    FileUpdateCreateRequest,
    ManualUpdateCreateRequest,
    PartnerUpdateEditRequest,
    PartnerUpdateListResponse,
    PartnerUpdateResponse,
)
from app.domains.contributor.updates.service import ContributorUpdateService
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse

router = APIRouter(
    prefix="/api/contributor/partners/{partner_id}/updates",
    tags=["contributor-updates"],
)


def get_contributor_update_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContributorUpdateService:
    return ContributorUpdateService(db)


@router.get("", response_model=PartnerUpdateListResponse)
async def list_updates(
    partner_id: uuid.UUID,
    service: Annotated[ContributorUpdateService, Depends(get_contributor_update_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
    cycle: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    status: PartnerUpdateStatus = PartnerUpdateStatus.pending,
    search: str | None = None,
) -> PartnerUpdateListResponse:
    return PartnerUpdateListResponse(
        updates=await service.list_updates(
            partner_id=partner_id,
            cycle=cycle,
            update_status=status,
            current_user=current_user,
            search=search,
        )
    )


@router.post("", response_model=PartnerUpdateResponse, status_code=http_status.HTTP_201_CREATED)
async def create_manual_update(
    partner_id: uuid.UUID,
    payload: ManualUpdateCreateRequest,
    service: Annotated[ContributorUpdateService, Depends(get_contributor_update_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
    cycle: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> PartnerUpdateResponse:
    return await service.create_manual_update(
        partner_id=partner_id,
        cycle=cycle,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/file",
    response_model=PartnerUpdateResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_file_update(
    partner_id: uuid.UUID,
    payload: FileUpdateCreateRequest,
    service: Annotated[ContributorUpdateService, Depends(get_contributor_update_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
    cycle: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> PartnerUpdateResponse:
    return await service.create_file_update(
        partner_id=partner_id,
        cycle=cycle,
        payload=payload,
        current_user=current_user,
    )


@router.patch("/{update_id}", response_model=PartnerUpdateResponse)
async def edit_pending_update(
    partner_id: uuid.UUID,
    update_id: uuid.UUID,
    payload: PartnerUpdateEditRequest,
    service: Annotated[ContributorUpdateService, Depends(get_contributor_update_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> PartnerUpdateResponse:
    return await service.edit_pending_update(
        partner_id=partner_id,
        update_id=update_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/{update_id}/approve", response_model=PartnerUpdateResponse)
async def approve_update(
    partner_id: uuid.UUID,
    update_id: uuid.UUID,
    service: Annotated[ContributorUpdateService, Depends(get_contributor_update_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> PartnerUpdateResponse:
    return await service.approve_update(
        partner_id=partner_id,
        update_id=update_id,
        current_user=current_user,
    )


@router.post("/{update_id}/dismiss", response_model=PartnerUpdateResponse)
async def dismiss_update(
    partner_id: uuid.UUID,
    update_id: uuid.UUID,
    service: Annotated[ContributorUpdateService, Depends(get_contributor_update_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> PartnerUpdateResponse:
    return await service.dismiss_update(
        partner_id=partner_id,
        update_id=update_id,
        current_user=current_user,
    )
