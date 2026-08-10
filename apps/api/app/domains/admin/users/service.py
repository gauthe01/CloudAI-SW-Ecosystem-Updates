import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_password
from app.db.models.identity import RoleType, User, UserStatus
from app.domains.admin.users.schemas import (
    AdminUserCreateRequest,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.schemas import UserResponse
from app.domains.identity.service import user_to_response


class AdminUserService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repository = IdentityRepository(db)

    async def list_users(self) -> list[AdminUserResponse]:
        users = await self.repository.list_users()
        return [admin_user_to_response(user) for user in users]

    async def create_user(self, payload: AdminUserCreateRequest) -> AdminUserResponse:
        existing = await self.repository.get_user_by_email(payload.email.lower())
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists.",
            )

        password_hash = (
            hash_password(self.settings.local_user_default_password)
            if self.settings.local_user_default_password
            else None
        )
        user = self.repository.add_user(
            email=payload.email,
            display_name=payload.display_name.strip(),
            roles=payload.roles,
            password_hash=password_hash,
        )
        await self.db.commit()
        return admin_user_to_response(user)

    async def update_user(
        self,
        *,
        user_id: uuid.UUID,
        payload: AdminUserUpdateRequest,
        current_admin: UserResponse,
    ) -> AdminUserResponse:
        user = await self._get_user_or_404(user_id)

        if payload.email is not None:
            requested_email = payload.email.lower()
            existing = await self.repository.get_user_by_email(requested_email)
            if existing is not None and existing.user_id != user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A user with this email already exists.",
                )
            user.email = requested_email

        if payload.display_name is not None:
            user.display_name = payload.display_name.strip()

        if payload.roles is not None:
            if user.user_id == current_admin.user_id and RoleType.admin not in payload.roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You cannot remove your own admin role.",
                )
            self.repository.replace_user_roles(user=user, roles=payload.roles)

        user.updated_at = datetime.now(UTC)
        await self.db.commit()
        return admin_user_to_response(user)

    async def deactivate_user(
        self,
        *,
        user_id: uuid.UUID,
        current_admin: UserResponse,
    ) -> AdminUserResponse:
        user = await self._get_user_or_404(user_id)
        if user.user_id == current_admin.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account.",
            )

        now = datetime.now(UTC)
        user.status = UserStatus.deactivated.value
        user.deactivated_at = now
        user.updated_at = now
        await self.repository.revoke_sessions_for_user(user.user_id)
        await self.db.commit()
        return admin_user_to_response(user)

    async def reactivate_user(self, user_id: uuid.UUID) -> AdminUserResponse:
        user = await self._get_user_or_404(user_id)
        user.status = UserStatus.active.value
        user.deactivated_at = None
        user.updated_at = datetime.now(UTC)
        await self.db.commit()
        return admin_user_to_response(user)

    async def _get_user_or_404(self, user_id: uuid.UUID) -> User:
        user = await self.repository.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user


def admin_user_to_response(user: User) -> AdminUserResponse:
    base_user = user_to_response(user)
    return AdminUserResponse(
        user_id=base_user.user_id,
        email=base_user.email,
        display_name=base_user.display_name,
        status=UserStatus(user.status),
        roles=base_user.roles,
        created_at=user.created_at,
        updated_at=user.updated_at,
        deactivated_at=user.deactivated_at,
    )
