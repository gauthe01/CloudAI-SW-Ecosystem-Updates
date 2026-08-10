import uuid

import pytest
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models.identity import (
    RoleType,
    User,
    UserLocalCredential,
    UserRoleAssignment,
    UserSession,
)
from app.db.session import get_session_factory
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.service import AuthService


@pytest.mark.asyncio
async def test_auth_service_login_me_and_logout_roundtrip() -> None:
    settings = get_settings()
    email = f"auth-test-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_user(session, email)
        repository = IdentityRepository(session)
        repository.add_user_with_local_password(
            email=email,
            display_name="Auth Test User",
            password_hash=hash_password("test-password"),
            roles=[RoleType.admin, RoleType.contributor],
        )
        await session.commit()

        service = AuthService(session, settings)
        login_result = await service.login(
            email=email,
            password="test-password",
            keep_signed_in=False,
            user_agent="pytest",
        )

        assert login_result.context.user.email == email
        assert set(login_result.context.user.roles) == {RoleType.admin, RoleType.contributor}
        assert login_result.context.available_views == [RoleType.contributor, RoleType.admin]
        assert login_result.context.active_view == RoleType.admin

        current_user = await service.get_user_from_token(login_result.raw_token)
        assert current_user.email == email

        await service.logout(login_result.raw_token)

        with pytest.raises(HTTPException):
            await service.get_user_from_token(login_result.raw_token)

        await cleanup_test_user(session, email)
        await session.commit()


@pytest.mark.asyncio
async def test_auth_service_defaults_admin_users_to_admin_view() -> None:
    settings = get_settings()
    email = f"admin-default-view-test-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_user(session, email)
        repository = IdentityRepository(session)
        repository.add_user_with_local_password(
            email=email,
            display_name="Admin Default View Test User",
            password_hash=hash_password("test-password"),
            roles=[RoleType.contributor, RoleType.presenter, RoleType.admin],
        )
        await session.commit()

        service = AuthService(session, settings)
        login_result = await service.login(
            email=email,
            password="test-password",
            keep_signed_in=False,
            user_agent="pytest",
        )

        assert login_result.context.available_views == [
            RoleType.contributor,
            RoleType.presenter,
            RoleType.admin,
        ]
        assert login_result.context.active_view == RoleType.admin

        await cleanup_test_user(session, email)
        await session.commit()


@pytest.mark.asyncio
async def test_auth_service_switches_active_view_only_when_allowed() -> None:
    settings = get_settings()
    email = f"view-switch-test-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_user(session, email)
        repository = IdentityRepository(session)
        repository.add_user_with_local_password(
            email=email,
            display_name="View Switch Test User",
            password_hash=hash_password("test-password"),
            roles=[RoleType.contributor, RoleType.presenter],
        )
        await session.commit()

        service = AuthService(session, settings)
        login_result = await service.login(
            email=email,
            password="test-password",
            keep_signed_in=False,
            user_agent="pytest",
        )

        assert login_result.context.available_views == [RoleType.contributor, RoleType.presenter]
        assert login_result.context.active_view == RoleType.contributor

        presenter_context = await service.switch_active_view(
            raw_token=login_result.raw_token,
            active_view=RoleType.presenter,
        )
        assert presenter_context.active_view == RoleType.presenter

        reloaded_context = await service.get_auth_context_from_token(login_result.raw_token)
        assert reloaded_context.active_view == RoleType.presenter

        with pytest.raises(HTTPException) as exc_info:
            await service.switch_active_view(
                raw_token=login_result.raw_token,
                active_view=RoleType.admin,
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

        await cleanup_test_user(session, email)
        await session.commit()


async def cleanup_test_user(session: AsyncSession, email: str) -> None:
    await session.execute(
        delete(UserSession).where(UserSession.user_id.in_(select_user_ids(email)))
    )
    await session.execute(
        delete(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(select_user_ids(email)))
    )
    await session.execute(
        delete(UserLocalCredential).where(UserLocalCredential.user_id.in_(select_user_ids(email)))
    )
    await session.execute(delete(User).where(User.email == email))


def select_user_ids(email: str):
    return select(User.user_id).where(User.email == email)
