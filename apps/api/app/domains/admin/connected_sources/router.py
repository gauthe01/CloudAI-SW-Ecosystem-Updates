import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.admin.connected_sources.schemas import (
    AdminConnectedSourceListResponse,
    AdminConnectedSourceResponse,
    AdminConnectedSourceReviewRequest,
)
from app.domains.admin.connected_sources.service import AdminConnectedSourceApprovalService
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse

router = APIRouter(prefix="/api/admin/connected-sources", tags=["admin-connected-sources"])


def get_admin_connected_source_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminConnectedSourceApprovalService:
    return AdminConnectedSourceApprovalService(db)


@router.get("", response_model=AdminConnectedSourceListResponse)
async def list_connected_sources(
    service: Annotated[
        AdminConnectedSourceApprovalService,
        Depends(get_admin_connected_source_service),
    ],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminConnectedSourceListResponse:
    return AdminConnectedSourceListResponse(connected_sources=await service.list_sources())


@router.post("/{connected_source_id}/test-access", response_model=AdminConnectedSourceResponse)
async def test_connected_source_access(
    connected_source_id: uuid.UUID,
    service: Annotated[
        AdminConnectedSourceApprovalService,
        Depends(get_admin_connected_source_service),
    ],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminConnectedSourceResponse:
    return await service.test_access(connected_source_id)


@router.post("/{connected_source_id}/approve", response_model=AdminConnectedSourceResponse)
async def approve_connected_source(
    connected_source_id: uuid.UUID,
    service: Annotated[
        AdminConnectedSourceApprovalService,
        Depends(get_admin_connected_source_service),
    ],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminConnectedSourceResponse:
    return await service.approve_source(
        connected_source_id=connected_source_id,
        current_admin=current_admin,
    )


@router.post("/{connected_source_id}/reject", response_model=AdminConnectedSourceResponse)
async def reject_connected_source(
    connected_source_id: uuid.UUID,
    payload: AdminConnectedSourceReviewRequest,
    service: Annotated[
        AdminConnectedSourceApprovalService,
        Depends(get_admin_connected_source_service),
    ],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminConnectedSourceResponse:
    return await service.reject_source(connected_source_id=connected_source_id, payload=payload)


@router.post(
    "/{connected_source_id}/needs-access-setup",
    response_model=AdminConnectedSourceResponse,
)
async def mark_connected_source_needs_access_setup(
    connected_source_id: uuid.UUID,
    payload: AdminConnectedSourceReviewRequest,
    service: Annotated[
        AdminConnectedSourceApprovalService,
        Depends(get_admin_connected_source_service),
    ],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminConnectedSourceResponse:
    return await service.mark_needs_access_setup(
        connected_source_id=connected_source_id,
        payload=payload,
    )


@router.post("/{connected_source_id}/disable", response_model=AdminConnectedSourceResponse)
async def disable_connected_source(
    connected_source_id: uuid.UUID,
    payload: AdminConnectedSourceReviewRequest,
    service: Annotated[
        AdminConnectedSourceApprovalService,
        Depends(get_admin_connected_source_service),
    ],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminConnectedSourceResponse:
    return await service.disable_source(connected_source_id=connected_source_id, payload=payload)
