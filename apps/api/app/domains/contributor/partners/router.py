import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.contributor.partners.schemas import (
    ContributorDashboardContextResponse,
    ContributorPartnerListResponse,
)
from app.domains.contributor.partners.service import ContributorPartnerService
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse

router = APIRouter(prefix="/api/contributor/partners", tags=["contributor-partners"])


def get_contributor_partner_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContributorPartnerService:
    return ContributorPartnerService(db)


@router.get("", response_model=ContributorPartnerListResponse)
async def list_assigned_partners(
    service: Annotated[ContributorPartnerService, Depends(get_contributor_partner_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> ContributorPartnerListResponse:
    return ContributorPartnerListResponse(
        partners=await service.list_assigned_partners(current_user),
    )


@router.get("/{partner_id}/dashboard-context", response_model=ContributorDashboardContextResponse)
async def get_dashboard_context(
    partner_id: uuid.UUID,
    service: Annotated[ContributorPartnerService, Depends(get_contributor_partner_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> ContributorDashboardContextResponse:
    return await service.get_dashboard_context(
        partner_id=partner_id,
        current_user=current_user,
    )
