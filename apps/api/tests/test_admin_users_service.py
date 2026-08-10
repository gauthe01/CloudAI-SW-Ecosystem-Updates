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
from app.domains.admin.users.schemas import AdminUserCreateRequest, AdminUserUpdateRequest
from app.domains.admin.users.service import AdminUserService
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.service import AuthService, user_to_response


@pytest.mark.asyncio
async def test_admin_can_create_user_with_roles_and_default_local_login() -> None:
    settings = get_settings()
    settings.local_user_default_password = "team-default-password"
    email = f"team-create-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_users(session, [email])
        service = AdminUserService(session, settings)

        created_user = await service.create_user(
            AdminUserCreateRequest(
                email=email,
                display_name="Created Team Member",
                roles=[RoleType.contributor, RoleType.presenter],
            )
        )

        assert created_user.email == email
        assert created_user.roles == [RoleType.contributor, RoleType.presenter]

        auth_service = AuthService(session, settings)
        login_result = await auth_service.login(
            email=email,
            password="team-default-password",
            keep_signed_in=False,
            user_agent="pytest",
        )
        assert login_result.context.available_views == [RoleType.contributor, RoleType.presenter]

        await cleanup_test_users(session, [email])
        await session.commit()


@pytest.mark.asyncio
async def test_admin_can_update_user_roles_and_reject_duplicate_email() -> None:
    settings = get_settings()
    member_email = f"team-update-{uuid.uuid4()}@example.com"
    duplicate_email = f"team-duplicate-{uuid.uuid4()}@example.com"
    admin_email = f"team-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_users(session, [member_email, duplicate_email, admin_email])
        repository = IdentityRepository(session)
        admin = repository.add_user_with_local_password(
            email=admin_email,
            display_name="Admin User",
            password_hash=hash_password("test-password"),
            roles=[RoleType.admin],
        )
        repository.add_user(
            email=duplicate_email,
            display_name="Duplicate User",
            roles=[RoleType.contributor],
        )
        member = repository.add_user(
            email=member_email,
            display_name="Team Member",
            roles=[RoleType.contributor],
        )
        await session.commit()

        service = AdminUserService(session, settings)
        current_admin = user_to_response(admin)
        updated_user = await service.update_user(
            user_id=member.user_id,
            payload=AdminUserUpdateRequest(
                display_name="Updated Team Member",
                roles=[RoleType.presenter, RoleType.admin],
            ),
            current_admin=current_admin,
        )

        assert updated_user.display_name == "Updated Team Member"
        assert updated_user.roles == [RoleType.presenter, RoleType.admin]

        with pytest.raises(HTTPException) as exc_info:
            await service.update_user(
                user_id=member.user_id,
                payload=AdminUserUpdateRequest(email=duplicate_email),
                current_admin=current_admin,
            )

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

        await cleanup_test_users(session, [member_email, duplicate_email, admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_admin_cannot_remove_own_admin_role_or_deactivate_self() -> None:
    settings = get_settings()
    admin_email = f"team-self-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_users(session, [admin_email])
        repository = IdentityRepository(session)
        admin = repository.add_user_with_local_password(
            email=admin_email,
            display_name="Self Admin",
            password_hash=hash_password("test-password"),
            roles=[RoleType.admin, RoleType.contributor],
        )
        await session.commit()

        service = AdminUserService(session, settings)
        current_admin = user_to_response(admin)

        with pytest.raises(HTTPException) as role_exc_info:
            await service.update_user(
                user_id=admin.user_id,
                payload=AdminUserUpdateRequest(roles=[RoleType.contributor]),
                current_admin=current_admin,
            )

        assert role_exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

        with pytest.raises(HTTPException) as deactivate_exc_info:
            await service.deactivate_user(user_id=admin.user_id, current_admin=current_admin)

        assert deactivate_exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

        await cleanup_test_users(session, [admin_email])
        await session.commit()


async def cleanup_test_users(session: AsyncSession, emails: list[str]) -> None:
    await session.execute(
        delete(UserSession).where(UserSession.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserLocalCredential).where(UserLocalCredential.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(delete(User).where(User.email.in_(emails)))


def select_user_ids(emails: list[str]):
    return select(User.user_id).where(User.email.in_(emails))
