import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.access_requests.schemas import (
    AccessRequestCreateRequest,
    AccessRequestCreateResponse,
    AdminAccessRequestApproveRequest,
    AdminAccessRequestListResponse,
    AdminAccessRequestReviewResponse,
)
from app.domains.access_requests.service import AccessRequestService
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse

public_router = APIRouter(prefix="/api/access-requests", tags=["access-requests"])
admin_router = APIRouter(prefix="/api/admin/access-requests", tags=["admin-access-requests"])


def get_access_request_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccessRequestService:
    return AccessRequestService(db)


@public_router.post(
    "",
    response_model=AccessRequestCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_access_request(
    payload: AccessRequestCreateRequest,
    service: Annotated[AccessRequestService, Depends(get_access_request_service)],
) -> AccessRequestCreateResponse:
    return await service.create_request(payload)


@admin_router.get("", response_model=AdminAccessRequestListResponse)
async def list_access_requests(
    service: Annotated[AccessRequestService, Depends(get_access_request_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminAccessRequestListResponse:
    return AdminAccessRequestListResponse(requests=await service.list_requests())


@admin_router.post("/{request_id}/approve", response_model=AdminAccessRequestReviewResponse)
async def approve_access_request(
    request_id: uuid.UUID,
    payload: AdminAccessRequestApproveRequest,
    service: Annotated[AccessRequestService, Depends(get_access_request_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminAccessRequestReviewResponse:
    return await service.approve_request(
        request_id=request_id,
        roles=payload.roles,
        current_admin=current_admin,
    )


@admin_router.post("/{request_id}/reject", response_model=AdminAccessRequestReviewResponse)
async def reject_access_request(
    request_id: uuid.UUID,
    service: Annotated[AccessRequestService, Depends(get_access_request_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminAccessRequestReviewResponse:
    return await service.reject_request(request_id=request_id, current_admin=current_admin)
