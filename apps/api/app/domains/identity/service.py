import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.db.models.identity import RoleType, User, UserStatus
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.schemas import AuthContextResponse, UserResponse

VIEW_PRIORITY = [RoleType.contributor, RoleType.presenter, RoleType.admin]
DEFAULT_ACTIVE_VIEW_PRIORITY = [RoleType.admin, RoleType.contributor, RoleType.presenter]


@dataclass(frozen=True)
class LoginResult:
    raw_token: str
    expires_at: datetime
    context: AuthContextResponse


class AuthService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repository = IdentityRepository(db)

    async def login(
        self,
        *,
        email: str,
        password: str,
        keep_signed_in: bool,
        user_agent: str | None,
    ) -> LoginResult:
        user = await self.repository.get_user_by_email(email.lower())
        if (
            user is None
            or user.status != UserStatus.active.value
            or user.local_credential is None
            or not verify_password(password, user.local_credential.password_hash)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        session_token = create_session_token(self.settings.app_secret_key)
        expires_at = self._session_expiry(keep_signed_in)
        active_view = default_active_view(user)
        self.repository.add_session(
            user=user,
            token_hash=session_token.token_hash,
            expires_at=expires_at,
            active_view=active_view,
            user_agent_hash=_hash_user_agent(user_agent),
        )
        await self.db.commit()
        return LoginResult(
            raw_token=session_token.raw,
            expires_at=expires_at,
            context=auth_context_from_user(user, active_view),
        )

    async def get_auth_context_from_token(self, raw_token: str | None) -> AuthContextResponse:
        if not raw_token:
            raise unauthorized()

        token_hash = hash_session_token(raw_token, self.settings.app_secret_key)
        row = await self.repository.get_user_by_session_hash(token_hash)
        if row is None:
            raise unauthorized()

        user, _session = row
        if user.status != UserStatus.active.value:
            raise unauthorized()

        active_view = _session.active_view
        available_views = available_views_for_user(user)
        if active_view not in available_views:
            active_view = default_active_view(user)
            _session.active_view = active_view
            await self.db.commit()

        return auth_context_from_user(user, active_view)

    async def get_user_from_token(self, raw_token: str | None) -> UserResponse:
        return (await self.get_auth_context_from_token(raw_token)).user

    async def switch_active_view(
        self,
        *,
        raw_token: str | None,
        active_view: RoleType,
    ) -> AuthContextResponse:
        if not raw_token:
            raise unauthorized()

        token_hash = hash_session_token(raw_token, self.settings.app_secret_key)
        row = await self.repository.get_user_by_session_hash(token_hash)
        if row is None:
            raise unauthorized()

        user, session = row
        if user.status != UserStatus.active.value:
            raise unauthorized()

        available_views = available_views_for_user(user)
        if active_view not in available_views:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This user cannot access the requested view.",
            )

        session.active_view = active_view
        await self.db.commit()
        return auth_context_from_user(user, active_view)

    async def logout(self, raw_token: str | None) -> None:
        if raw_token:
            token_hash = hash_session_token(raw_token, self.settings.app_secret_key)
            await self.repository.revoke_session(token_hash)
            await self.db.commit()

    async def bootstrap_local_admin(self) -> User | None:
        if not self.settings.bootstrap_admin_email or not self.settings.bootstrap_admin_password:
            return None

        existing = await self.repository.get_user_by_email(self.settings.bootstrap_admin_email)
        if existing is not None:
            return existing

        user = self.repository.add_user_with_local_password(
            email=self.settings.bootstrap_admin_email,
            display_name=self.settings.bootstrap_admin_display_name,
            password_hash=hash_password(self.settings.bootstrap_admin_password),
            roles=[RoleType.admin, RoleType.contributor, RoleType.presenter],
        )
        await self.db.commit()
        return user

    def _session_expiry(self, keep_signed_in: bool) -> datetime:
        if keep_signed_in:
            return datetime.now(UTC) + timedelta(days=self.settings.session_ttl_days)
        return datetime.now(UTC) + timedelta(hours=self.settings.session_short_ttl_hours)


def user_to_response(user: User) -> UserResponse:
    roles = sorted(
        (assignment.role_type for assignment in user.role_assignments),
        key=lambda role: VIEW_PRIORITY.index(role),
    )
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        roles=roles,
    )


def available_views_for_user(user: User) -> list[RoleType]:
    roles = {assignment.role_type for assignment in user.role_assignments}
    return [view for view in VIEW_PRIORITY if view in roles]


def default_active_view(user: User) -> RoleType:
    available_views = available_views_for_user(user)
    if not available_views:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user has no assigned application views.",
        )
    return next(view for view in DEFAULT_ACTIVE_VIEW_PRIORITY if view in available_views)


def auth_context_from_user(user: User, active_view: RoleType) -> AuthContextResponse:
    available_views = available_views_for_user(user)
    if active_view not in available_views:
        active_view = default_active_view(user)
    return AuthContextResponse(
        user=user_to_response(user),
        available_views=available_views,
        active_view=active_view,
    )


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
    )


def _hash_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()
