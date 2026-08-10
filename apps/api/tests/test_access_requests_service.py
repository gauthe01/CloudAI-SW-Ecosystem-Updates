import uuid

import pytest
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models.account_access_request import (
    AccountAccessRequest,
    AccountAccessRequestStatus,
)
from app.db.models.identity import (
    RoleType,
    User,
    UserLocalCredential,
    UserRoleAssignment,
    UserSession,
)
from app.db.session import get_session_factory
from app.domains.access_requests.repository import AccessRequestRepository
from app.domains.access_requests.schemas import AccessRequestCreateRequest
from app.domains.access_requests.service import AccessRequestService
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.service import user_to_response


@pytest.mark.asyncio
async def test_access_request_stores_pending_hashed_password() -> None:
    email = f"access-request-{uuid.uuid4()}@arm.com"

    async with get_session_factory()() as session:
        await cleanup_access_request_users(session, [email])
        service = AccessRequestService(session)

        response = await service.create_request(
            AccessRequestCreateRequest(
                display_name="Access Requester",
                email=email,
                password="Local-dev-1!",
                confirm_password="Local-dev-1!",
            )
        )

        assert response.status == AccountAccessRequestStatus.pending

        request = await AccessRequestRepository(session).get_pending_by_email(email)
        assert request is not None
        assert request.password_hash != "Local-dev-1!"
        assert verify_password("Local-dev-1!", request.password_hash)

        await cleanup_access_request_users(session, [email])
        await session.commit()


@pytest.mark.asyncio
async def test_access_request_rejects_existing_user_and_pending_duplicate() -> None:
    existing_email = f"access-existing-{uuid.uuid4()}@arm.com"
    pending_email = f"access-pending-{uuid.uuid4()}@arm.com"

    async with get_session_factory()() as session:
        await cleanup_access_request_users(session, [existing_email, pending_email])
        repository = IdentityRepository(session)
        repository.add_user(
            email=existing_email,
            display_name="Existing User",
            roles=[RoleType.presenter],
        )
        await session.commit()

        service = AccessRequestService(session)
        with pytest.raises(HTTPException) as existing_exc:
            await service.create_request(
                AccessRequestCreateRequest(
                    display_name="Existing User",
                    email=existing_email,
                    password="Local-dev-1!",
                    confirm_password="Local-dev-1!",
                )
            )

        assert existing_exc.value.status_code == status.HTTP_409_CONFLICT

        payload = AccessRequestCreateRequest(
            display_name="Pending User",
            email=pending_email,
            password="Local-dev-1!",
            confirm_password="Local-dev-1!",
        )
        await service.create_request(payload)

        with pytest.raises(HTTPException) as pending_exc:
            await service.create_request(payload)

        assert pending_exc.value.status_code == status.HTTP_409_CONFLICT

        await cleanup_access_request_users(session, [existing_email, pending_email])
        await session.commit()


@pytest.mark.asyncio
async def test_admin_can_approve_access_request_with_roles() -> None:
    admin_email = f"access-admin-{uuid.uuid4()}@arm.com"
    requester_email = f"access-approved-{uuid.uuid4()}@arm.com"

    async with get_session_factory()() as session:
        await cleanup_access_request_users(session, [admin_email, requester_email])
        repository = IdentityRepository(session)
        admin = repository.add_user_with_local_password(
            email=admin_email,
            display_name="Access Admin",
            password_hash=hash_password("Local-dev-1!"),
            roles=[RoleType.admin],
        )
        await session.commit()

        service = AccessRequestService(session)
        await service.create_request(
            AccessRequestCreateRequest(
                display_name="Approved User",
                email=requester_email,
                password="Local-dev-1!",
                confirm_password="Local-dev-1!",
            )
        )
        request = await AccessRequestRepository(session).get_pending_by_email(requester_email)
        assert request is not None

        result = await service.approve_request(
            request_id=request.request_id,
            roles=[RoleType.presenter],
            current_admin=user_to_response(admin),
        )

        assert result.request.status == AccountAccessRequestStatus.approved
        assert result.created_user is not None
        assert result.request.created_user_id == result.created_user.user_id
        assert result.created_user.email == requester_email
        assert result.created_user.roles == [RoleType.presenter]

        created_user = await repository.get_user_by_email(requester_email)
        assert created_user is not None
        assert created_user.local_credential is not None
        assert verify_password("Local-dev-1!", created_user.local_credential.password_hash)

        await cleanup_access_request_users(session, [admin_email, requester_email])
        await session.commit()


@pytest.mark.asyncio
async def test_admin_cannot_approve_access_request_without_roles() -> None:
    admin_email = f"access-admin-no-role-{uuid.uuid4()}@arm.com"
    requester_email = f"access-no-role-{uuid.uuid4()}@arm.com"

    async with get_session_factory()() as session:
        await cleanup_access_request_users(session, [admin_email, requester_email])
        repository = IdentityRepository(session)
        admin = repository.add_user_with_local_password(
            email=admin_email,
            display_name="Access Admin",
            password_hash=hash_password("Local-dev-1!"),
            roles=[RoleType.admin],
        )
        await session.commit()

        service = AccessRequestService(session)
        await service.create_request(
            AccessRequestCreateRequest(
                display_name="No Role User",
                email=requester_email,
                password="Local-dev-1!",
                confirm_password="Local-dev-1!",
            )
        )
        request = await AccessRequestRepository(session).get_pending_by_email(requester_email)
        assert request is not None

        with pytest.raises(HTTPException) as exc_info:
            await service.approve_request(
                request_id=request.request_id,
                roles=[],
                current_admin=user_to_response(admin),
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert await repository.get_user_by_email(requester_email) is None

        await cleanup_access_request_users(session, [admin_email, requester_email])
        await session.commit()


@pytest.mark.asyncio
async def test_admin_can_reject_access_request() -> None:
    admin_email = f"access-reject-admin-{uuid.uuid4()}@arm.com"
    requester_email = f"access-rejected-{uuid.uuid4()}@arm.com"

    async with get_session_factory()() as session:
        await cleanup_access_request_users(session, [admin_email, requester_email])
        repository = IdentityRepository(session)
        admin = repository.add_user_with_local_password(
            email=admin_email,
            display_name="Access Admin",
            password_hash=hash_password("Local-dev-1!"),
            roles=[RoleType.admin],
        )
        await session.commit()

        service = AccessRequestService(session)
        await service.create_request(
            AccessRequestCreateRequest(
                display_name="Rejected User",
                email=requester_email,
                password="Local-dev-1!",
                confirm_password="Local-dev-1!",
            )
        )
        request = await AccessRequestRepository(session).get_pending_by_email(requester_email)
        assert request is not None

        result = await service.reject_request(
            request_id=request.request_id,
            current_admin=user_to_response(admin),
        )

        assert result.request.status == AccountAccessRequestStatus.rejected
        assert result.created_user is None
        assert await repository.get_user_by_email(requester_email) is None

        await cleanup_access_request_users(session, [admin_email, requester_email])
        await session.commit()


async def cleanup_access_request_users(session: AsyncSession, emails: list[str]) -> None:
    await session.execute(
        delete(AccountAccessRequest).where(AccountAccessRequest.email.in_(emails))
    )
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
