import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.identity import (
    RoleType,
    User,
    UserLocalCredential,
    UserRoleAssignment,
    UserSession,
)


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        statement = (
            select(User)
            .options(
                selectinload(User.local_credential),
                selectinload(User.role_assignments),
            )
            .where(User.email == email.lower())
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        statement = (
            select(User)
            .options(
                selectinload(User.local_credential),
                selectinload(User.role_assignments),
            )
            .where(User.user_id == user_id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        statement = (
            select(User)
            .options(
                selectinload(User.local_credential),
                selectinload(User.role_assignments),
            )
            .order_by(User.display_name.asc(), User.email.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_user_by_session_hash(self, token_hash: str) -> tuple[User, UserSession] | None:
        statement = (
            select(User, UserSession)
            .join(UserSession, UserSession.user_id == User.user_id)
            .options(selectinload(User.role_assignments))
            .where(UserSession.session_token_hash == token_hash)
            .where(UserSession.revoked_at.is_(None))
            .where(UserSession.expires_at > datetime.now(UTC))
        )
        result = await self.session.execute(statement)
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    def add_user_with_local_password(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        roles: list[RoleType],
    ) -> User:
        user = User(email=email.lower(), display_name=display_name)
        user.local_credential = UserLocalCredential(password_hash=password_hash)
        user.role_assignments = [UserRoleAssignment(role_type=role) for role in roles]
        self.session.add(user)
        return user

    def add_user(
        self,
        *,
        email: str,
        display_name: str,
        roles: list[RoleType],
        password_hash: str | None = None,
    ) -> User:
        user = User(email=email.lower(), display_name=display_name)
        if password_hash:
            user.local_credential = UserLocalCredential(password_hash=password_hash)
        self.session.add(user)
        self.replace_user_roles(user=user, roles=roles)
        return user

    def replace_user_roles(self, *, user: User, roles: list[RoleType]) -> None:
        user.role_assignments = [UserRoleAssignment(role_type=role) for role in roles]

    async def revoke_sessions_for_user(self, user_id: uuid.UUID) -> None:
        statement = select(UserSession).where(UserSession.user_id == user_id)
        result = await self.session.execute(statement)
        now = datetime.now(UTC)
        for session in result.scalars():
            if session.revoked_at is None:
                session.revoked_at = now

    async def revoke_sessions_for_user_except(
        self,
        *,
        user_id: uuid.UUID,
        except_session_id: uuid.UUID | None,
    ) -> None:
        statement = select(UserSession).where(UserSession.user_id == user_id)
        result = await self.session.execute(statement)
        now = datetime.now(UTC)
        for session in result.scalars():
            if session.session_id != except_session_id and session.revoked_at is None:
                session.revoked_at = now

    async def delete_user_roles(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id)
        )

    def add_session(
        self,
        *,
        user: User,
        token_hash: str,
        expires_at: datetime,
        active_view: RoleType,
        user_agent_hash: str | None,
    ) -> UserSession:
        session = UserSession(
            user_id=user.user_id,
            session_token_hash=token_hash,
            expires_at=expires_at,
            active_view=active_view,
            user_agent_hash=user_agent_hash,
        )
        self.session.add(session)
        return session

    async def revoke_session(self, token_hash: str) -> None:
        statement = select(UserSession).where(UserSession.session_token_hash == token_hash)
        result = await self.session.execute(statement)
        session = result.scalar_one_or_none()
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
