import uuid
from datetime import date
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.runtime.client import AIRuntimeConfigurationError, build_ai_client_runtime
from app.core.config import get_settings
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
    PresenterVoiceSpeechRequest,
    PresenterVoiceTranscriptResponse,
)
from app.domains.presenter.service import PresenterService

router = APIRouter(prefix="/api/presenter", tags=["presenter"])

VOICE_AUDIO_MAX_BYTES = 8 * 1024 * 1024
VOICE_AUDIO_MAX_DURATION_MS = 60_000
VOICE_AUDIO_CONTENT_TYPES = {
    "audio/webm",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-m4a",
}


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


@router.post("/ask/voice/transcribe", response_model=PresenterVoiceTranscriptResponse)
async def transcribe_presenter_ai_voice(
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
    audio: Annotated[UploadFile, File()],
    duration_ms: Annotated[int | None, Form()] = None,
) -> PresenterVoiceTranscriptResponse:
    if duration_ms is not None and duration_ms > VOICE_AUDIO_MAX_DURATION_MS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio is longer than 60 seconds.",
        )
    content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in VOICE_AUDIO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio type.",
        )
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio is empty.")
    if len(data) > VOICE_AUDIO_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio is larger than 8 MB.",
        )
    try:
        runtime = build_ai_client_runtime()
    except AIRuntimeConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    try:
        transcript = await runtime.client.audio.transcriptions.create(
            model=get_settings().ai_model_audio_transcription,
            file=(audio.filename or "question.webm", data, content_type),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not transcribe audio: {exc}",
        ) from exc
    text = " ".join((getattr(transcript, "text", "") or "").split())
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No speech detected.",
        )
    return PresenterVoiceTranscriptResponse(text=text)


@router.post("/ask/voice/speech")
async def synthesize_presenter_ai_voice(
    payload: PresenterVoiceSpeechRequest,
    _: Annotated[UserResponse, Depends(require_roles(RoleType.presenter))],
) -> Response:
    text = " ".join(payload.text.split())
    if len(text) > 1600:
        text = text[:1600].rsplit(" ", 1)[0] + "..."
    try:
        runtime = build_ai_client_runtime()
    except AIRuntimeConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    try:
        speech = await runtime.client.audio.speech.create(
            model=get_settings().ai_model_audio_speech,
            voice=get_settings().ai_audio_voice,
            input=text,
            response_format="mp3",
        )
        audio_bytes = await read_audio_response_bytes(speech)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not generate speech: {exc}",
        ) from exc
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate speech.",
        )
    return Response(content=audio_bytes, media_type="audio/mpeg")


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


async def read_audio_response_bytes(response: object) -> bytes:
    if hasattr(response, "read"):
        content = response.read()
        if hasattr(content, "__await__"):
            content = await content
        return bytes(content or b"")
    content = getattr(response, "content", None)
    if hasattr(content, "__await__"):
        content = await content
    if isinstance(content, (bytes, bytearray)):
        return bytes(content)
    if isinstance(response, (bytes, bytearray)):
        return bytes(response)
    return b""
