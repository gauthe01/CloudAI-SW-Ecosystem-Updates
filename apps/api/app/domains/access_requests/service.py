import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.account_access_request import (
    AccountAccessRequest,
    AccountAccessRequestStatus,
)
from app.db.models.identity import RoleType
from app.domains.access_requests.repository import AccessRequestRepository
from app.domains.access_requests.schemas import (
    AccessRequestCreateRequest,
    AccessRequestCreateResponse,
    AdminAccessRequestResponse,
    AdminAccessRequestReviewResponse,
)
from app.domains.admin.users.service import admin_user_to_response
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.schemas import UserResponse


class AccessRequestService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.requests = AccessRequestRepository(db)
        self.identity = IdentityRepository(db)

    async def create_request(
        self,
        payload: AccessRequestCreateRequest,
    ) -> AccessRequestCreateResponse:
        existing_user = await self.identity.get_user_by_email(payload.email)
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this ARM email already exists.",
            )

        pending_request = await self.requests.get_pending_by_email(payload.email)
        if pending_request is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An access request for this ARM email is already pending.",
            )

        self.requests.add_request(
            email=payload.email,
            display_name=payload.display_name.strip(),
            password_hash=hash_password(payload.password),
        )
        await self.db.commit()
        return AccessRequestCreateResponse(
            status=AccountAccessRequestStatus.pending,
            message="Access request submitted for admin review.",
        )

    async def list_requests(self) -> list[AdminAccessRequestResponse]:
        requests = await self.requests.list_requests()
        return [access_request_to_response(request) for request in requests]

    async def approve_request(
        self,
        *,
        request_id: uuid.UUID,
        roles: list[RoleType],
        current_admin: UserResponse,
    ) -> AdminAccessRequestReviewResponse:
        if not roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select at least one role before approving access.",
            )

        request = await self._get_pending_request_or_404(request_id)
        existing_user = await self.identity.get_user_by_email(request.email)
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists.",
            )

        user = self.identity.add_user(
            email=request.email,
            display_name=request.display_name,
            roles=roles,
            password_hash=request.password_hash,
        )
        await self.db.flush()
        now = datetime.now(UTC)
        request.status = AccountAccessRequestStatus.approved.value
        request.reviewed_by = current_admin.user_id
        request.reviewed_at = now
        request.created_user_id = user.user_id
        await self.db.commit()
        return AdminAccessRequestReviewResponse(
            request=access_request_to_response(request),
            created_user=admin_user_to_response(user),
        )

    async def reject_request(
        self,
        *,
        request_id: uuid.UUID,
        current_admin: UserResponse,
    ) -> AdminAccessRequestReviewResponse:
        request = await self._get_pending_request_or_404(request_id)
        request.status = AccountAccessRequestStatus.rejected.value
        request.reviewed_by = current_admin.user_id
        request.reviewed_at = datetime.now(UTC)
        await self.db.commit()
        return AdminAccessRequestReviewResponse(request=access_request_to_response(request))

    async def _get_pending_request_or_404(self, request_id: uuid.UUID) -> AccountAccessRequest:
        request = await self.requests.get_by_id(request_id)
        if request is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Access request not found.",
            )
        if request.status != AccountAccessRequestStatus.pending.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access request has already been reviewed.",
            )
        return request


def access_request_to_response(request: AccountAccessRequest) -> AdminAccessRequestResponse:
    return AdminAccessRequestResponse(
        request_id=request.request_id,
        email=request.email,
        display_name=request.display_name,
        status=AccountAccessRequestStatus(request.status),
        requested_at=request.requested_at,
        reviewed_at=request.reviewed_at,
        reviewed_by=request.reviewed_by,
        created_user_id=request.created_user_id,
    )
