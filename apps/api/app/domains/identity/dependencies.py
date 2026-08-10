from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.identity.schemas import AuthContextResponse, UserResponse
from app.domains.identity.service import AuthService


def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(db, settings)


async def get_current_auth_context(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    session_token: Annotated[
        str | None,
        Cookie(alias="cloud_ai_software_ecosystem_updates_session"),
    ] = None,
) -> AuthContextResponse:
    return await auth_service.get_auth_context_from_token(session_token)


async def get_current_user(
    auth_context: Annotated[AuthContextResponse, Depends(get_current_auth_context)],
) -> UserResponse:
    return auth_context.user


def require_roles(*allowed_roles: RoleType):
    async def dependency(
        current_user: Annotated[UserResponse, Depends(get_current_user)],
    ) -> UserResponse:
        if not set(current_user.roles).intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This user does not have access to this resource.",
            )
        return current_user

    return dependency
