import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.contributor.connected_sources.schemas import (
    ConnectedSourceListResponse,
    ConnectedSourceRequest,
    ConnectedSourceResponse,
)
from app.domains.contributor.connected_sources.service import ContributorConnectedSourceService
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse

router = APIRouter(
    prefix="/api/contributor/partners/{partner_id}/connected-sources",
    tags=["contributor-connected-sources"],
)


def get_connected_source_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContributorConnectedSourceService:
    return ContributorConnectedSourceService(db)


@router.get("", response_model=ConnectedSourceListResponse)
async def list_connected_sources(
    partner_id: uuid.UUID,
    service: Annotated[ContributorConnectedSourceService, Depends(get_connected_source_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> ConnectedSourceListResponse:
    return ConnectedSourceListResponse(
        connected_sources=await service.list_sources(
            partner_id=partner_id,
            current_user=current_user,
        )
    )


@router.post("", response_model=ConnectedSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_connected_source(
    partner_id: uuid.UUID,
    payload: ConnectedSourceRequest,
    service: Annotated[ContributorConnectedSourceService, Depends(get_connected_source_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> ConnectedSourceResponse:
    return await service.create_source(
        partner_id=partner_id,
        payload=payload,
        current_user=current_user,
    )


@router.patch("/{connected_source_id}", response_model=ConnectedSourceResponse)
async def update_connected_source(
    partner_id: uuid.UUID,
    connected_source_id: uuid.UUID,
    payload: ConnectedSourceRequest,
    service: Annotated[ContributorConnectedSourceService, Depends(get_connected_source_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> ConnectedSourceResponse:
    return await service.update_source(
        partner_id=partner_id,
        connected_source_id=connected_source_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/{connected_source_id}/archive", response_model=ConnectedSourceResponse)
async def archive_connected_source(
    partner_id: uuid.UUID,
    connected_source_id: uuid.UUID,
    service: Annotated[ContributorConnectedSourceService, Depends(get_connected_source_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> ConnectedSourceResponse:
    return await service.archive_source(
        partner_id=partner_id,
        connected_source_id=connected_source_id,
        current_user=current_user,
    )


@router.post("/{connected_source_id}/pause", response_model=ConnectedSourceResponse)
async def pause_connected_source(
    partner_id: uuid.UUID,
    connected_source_id: uuid.UUID,
    service: Annotated[ContributorConnectedSourceService, Depends(get_connected_source_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> ConnectedSourceResponse:
    return await service.pause_source(
        partner_id=partner_id,
        connected_source_id=connected_source_id,
        current_user=current_user,
    )


@router.post("/{connected_source_id}/resume", response_model=ConnectedSourceResponse)
async def resume_connected_source(
    partner_id: uuid.UUID,
    connected_source_id: uuid.UUID,
    service: Annotated[ContributorConnectedSourceService, Depends(get_connected_source_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> ConnectedSourceResponse:
    return await service.resume_source(
        partner_id=partner_id,
        connected_source_id=connected_source_id,
        current_user=current_user,
    )
