import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.contributor.metadata.schemas import (
    PartnerMetadataResponse,
    PartnerMetadataSaveRequest,
)
from app.domains.contributor.metadata.service import ContributorMetadataService
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse

router = APIRouter(
    prefix="/api/contributor/partners/{partner_id}/metadata",
    tags=["contributor-metadata"],
)


def get_contributor_metadata_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContributorMetadataService:
    return ContributorMetadataService(db)


@router.get("", response_model=PartnerMetadataResponse)
async def get_metadata(
    partner_id: uuid.UUID,
    service: Annotated[ContributorMetadataService, Depends(get_contributor_metadata_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
    cycle: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> PartnerMetadataResponse:
    return await service.get_metadata(
        partner_id=partner_id,
        cycle=cycle,
        current_user=current_user,
    )


@router.put("", response_model=PartnerMetadataResponse)
async def save_metadata(
    partner_id: uuid.UUID,
    payload: PartnerMetadataSaveRequest,
    service: Annotated[ContributorMetadataService, Depends(get_contributor_metadata_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
    cycle: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> PartnerMetadataResponse:
    return await service.save_metadata(
        partner_id=partner_id,
        cycle=cycle,
        payload=payload,
        current_user=current_user,
    )
