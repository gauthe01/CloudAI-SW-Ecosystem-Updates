import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.account_access_request import (
    AccountAccessRequest,
    AccountAccessRequestStatus,
)


class AccessRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, request_id: uuid.UUID) -> AccountAccessRequest | None:
        result = await self.session.execute(
            select(AccountAccessRequest).where(AccountAccessRequest.request_id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_by_email(self, email: str) -> AccountAccessRequest | None:
        result = await self.session.execute(
            select(AccountAccessRequest)
            .where(AccountAccessRequest.email == email.lower())
            .where(AccountAccessRequest.status == AccountAccessRequestStatus.pending.value)
        )
        return result.scalar_one_or_none()

    async def list_requests(self) -> list[AccountAccessRequest]:
        result = await self.session.execute(
            select(AccountAccessRequest).order_by(
                AccountAccessRequest.requested_at.desc(),
                AccountAccessRequest.email.asc(),
            )
        )
        return list(result.scalars().all())

    def add_request(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: str,
    ) -> AccountAccessRequest:
        request = AccountAccessRequest(
            email=email.lower(),
            display_name=display_name,
            password_hash=password_hash,
        )
        self.session.add(request)
        return request
