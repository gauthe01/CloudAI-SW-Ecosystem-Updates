import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse
from app.domains.presenter.schemas import (
    DraftEmailRequest,
    DraftEmailResponse,
    PresenterAnalysisResponse,
    PresenterMetadataResponse,
    PresenterPartnerListResponse,
    PresenterUpdateListResponse,
)
from app.domains.presenter.service import PresenterService

router = APIRouter(prefix="/api/presenter", tags=["presenter"])


def get_presenter_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PresenterService:
    return PresenterService(db)


@router.get("/partners", response_model=PresenterPartnerListResponse)
async def list_presenter_partners(
    service: Annotated[PresenterService, Depends(get_presenter_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
    cycle: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> PresenterPartnerListResponse:
    return PresenterPartnerListResponse(partners=await service.list_partners(cycle=cycle))


@router.get("/updates", response_model=PresenterUpdateListResponse)
async def list_presenter_updates(
    service: Annotated[PresenterService, Depends(get_presenter_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
    cycle: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    partner_id: uuid.UUID | None = None,
    partner_ids: list[uuid.UUID] | None = Query(default=None),
    search: str | None = None,
) -> PresenterUpdateListResponse:
    return PresenterUpdateListResponse(
        updates=await service.list_approved_updates(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids or [],
            search=search,
        )
    )


@router.get("/partners/{partner_id}/metadata", response_model=PresenterMetadataResponse)
async def get_presenter_partner_metadata(
    partner_id: uuid.UUID,
    service: Annotated[PresenterService, Depends(get_presenter_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
    cycle: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> PresenterMetadataResponse:
    return await service.get_partner_metadata(cycle=cycle, partner_id=partner_id)


@router.get("/analysis", response_model=PresenterAnalysisResponse)
async def get_presenter_analysis(
    service: Annotated[PresenterService, Depends(get_presenter_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
    cycle: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    partner_id: uuid.UUID | None = None,
    partner_ids: list[uuid.UUID] | None = Query(default=None),
) -> PresenterAnalysisResponse:
    return await service.get_analysis(
        cycle=cycle,
        partner_id=partner_id,
        partner_ids=partner_ids or [],
    )


@router.post("/draft-email", response_model=DraftEmailResponse)
async def draft_presenter_email(
    payload: DraftEmailRequest,
    service: Annotated[PresenterService, Depends(get_presenter_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
) -> DraftEmailResponse:
    return await service.draft_email(
        cycle=payload.cycle,
        partner_id=payload.partner_id,
        partner_ids=payload.partner_ids,
    )
