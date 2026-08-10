import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.admin.users.schemas import (
    AdminUserCreateRequest,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from app.domains.admin.users.service import AdminUserService
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


def get_admin_user_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminUserService:
    return AdminUserService(db, settings)


@router.get("", response_model=AdminUserListResponse)
async def list_users(
    service: Annotated[AdminUserService, Depends(get_admin_user_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminUserListResponse:
    return AdminUserListResponse(users=await service.list_users())


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreateRequest,
    service: Annotated[AdminUserService, Depends(get_admin_user_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminUserResponse:
    return await service.create_user(payload)


@router.patch("/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdateRequest,
    service: Annotated[AdminUserService, Depends(get_admin_user_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminUserResponse:
    return await service.update_user(
        user_id=user_id,
        payload=payload,
        current_admin=current_admin,
    )


@router.post("/{user_id}/deactivate", response_model=AdminUserResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    service: Annotated[AdminUserService, Depends(get_admin_user_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminUserResponse:
    return await service.deactivate_user(user_id=user_id, current_admin=current_admin)


@router.post("/{user_id}/reactivate", response_model=AdminUserResponse)
async def reactivate_user(
    user_id: uuid.UUID,
    service: Annotated[AdminUserService, Depends(get_admin_user_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> AdminUserResponse:
    return await service.reactivate_user(user_id)
