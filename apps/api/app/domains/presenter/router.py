import uuid
from datetime import date
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
    PresenterAskRequest,
    PresenterAskResponse,
    PresenterDecisionBoardRequest,
    PresenterDecisionBoardResponse,
    PresenterExecutiveSummaryRequest,
    PresenterExecutiveSummaryResponse,
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
    date_start: date | None = None,
    date_end: date | None = None,
) -> PresenterPartnerListResponse:
    return PresenterPartnerListResponse(
        partners=await service.list_partners(
            cycle=cycle,
            date_start=date_start,
            date_end=date_end,
        )
    )


@router.get("/updates", response_model=PresenterUpdateListResponse)
async def list_presenter_updates(
    service: Annotated[PresenterService, Depends(get_presenter_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
    cycle: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    partner_id: uuid.UUID | None = None,
    partner_ids: Annotated[list[uuid.UUID] | None, Query()] = None,
    search: str | None = None,
    date_start: date | None = None,
    date_end: date | None = None,
) -> PresenterUpdateListResponse:
    return PresenterUpdateListResponse(
        updates=await service.list_approved_updates(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids or [],
            search=search,
            date_start=date_start,
            date_end=date_end,
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
    partner_ids: Annotated[list[uuid.UUID] | None, Query()] = None,
    date_start: date | None = None,
    date_end: date | None = None,
) -> PresenterAnalysisResponse:
    return await service.get_analysis(
        cycle=cycle,
        partner_id=partner_id,
        partner_ids=partner_ids or [],
        date_start=date_start,
        date_end=date_end,
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
        date_start=payload.date_start,
        date_end=payload.date_end,
    )


@router.post("/ask", response_model=PresenterAskResponse)
async def ask_presenter_ai(
    payload: PresenterAskRequest,
    service: Annotated[PresenterService, Depends(get_presenter_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
) -> PresenterAskResponse:
    return await service.ask_ai(
        cycle=payload.cycle,
        question=payload.question,
        partner_id=payload.partner_id,
        partner_ids=payload.partner_ids,
        date_start=payload.date_start,
        date_end=payload.date_end,
    )


@router.post("/executive-summary", response_model=PresenterExecutiveSummaryResponse)
async def generate_presenter_executive_summary(
    payload: PresenterExecutiveSummaryRequest,
    service: Annotated[PresenterService, Depends(get_presenter_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
) -> PresenterExecutiveSummaryResponse:
    return await service.generate_executive_summary(
        cycle=payload.cycle,
        partner_id=payload.partner_id,
        partner_ids=payload.partner_ids,
        date_start=payload.date_start,
        date_end=payload.date_end,
    )


@router.post("/decision-board", response_model=PresenterDecisionBoardResponse)
async def generate_presenter_decision_board(
    payload: PresenterDecisionBoardRequest,
    service: Annotated[PresenterService, Depends(get_presenter_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
) -> PresenterDecisionBoardResponse:
    return await service.generate_decision_board(
        cycle=payload.cycle,
        partner_id=payload.partner_id,
        partner_ids=payload.partner_ids,
        date_start=payload.date_start,
        date_end=payload.date_end,
    )
