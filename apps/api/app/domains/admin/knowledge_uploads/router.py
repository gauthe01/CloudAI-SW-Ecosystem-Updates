import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse
from app.domains.uploads.schemas import (
    KnowledgeUploadCandidateResponse,
    KnowledgeUploadCandidateUpdateRequest,
    KnowledgeUploadCommitRequest,
    KnowledgeUploadCommitResponse,
    KnowledgeUploadDetailResponse,
    KnowledgeUploadListResponse,
    KnowledgeUploadMappingsRequest,
    KnowledgeUploadResponse,
    KnowledgeUploadSessionDetailResponse,
    KnowledgeUploadStageRequest,
    KnowledgeUploadStageResponse,
)
from app.domains.uploads.service import KnowledgeUploadService

router = APIRouter(prefix="/api/admin/knowledge-uploads", tags=["admin-knowledge-uploads"])


def get_knowledge_upload_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeUploadService:
    return KnowledgeUploadService(db, settings)


@router.get("", response_model=KnowledgeUploadListResponse)
async def list_knowledge_uploads(
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
    partner_id: Annotated[uuid.UUID | None, Query()] = None,
) -> KnowledgeUploadListResponse:
    return KnowledgeUploadListResponse(
        uploads=await service.list_admin_uploads(partner_id=partner_id)
    )


@router.post("", response_model=KnowledgeUploadResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_upload(
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    partner_id: Annotated[uuid.UUID | None, Form()] = None,
) -> KnowledgeUploadResponse:
    return await service.create_admin_upload(
        file=file,
        current_user=current_admin,
        partner_id=partner_id,
        title=title,
        description=description,
    )


@router.post(
    "/sessions",
    response_model=KnowledgeUploadSessionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_upload_session(
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
    files: Annotated[list[UploadFile], File()],
) -> KnowledgeUploadSessionDetailResponse:
    return await service.create_admin_session(files=files, current_user=current_admin)


@router.get("/sessions/{session_id}", response_model=KnowledgeUploadSessionDetailResponse)
async def get_knowledge_upload_session(
    session_id: uuid.UUID,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> KnowledgeUploadSessionDetailResponse:
    return await service.get_admin_session_detail(session_id=session_id)


@router.post("/sessions/{session_id}/mappings", response_model=KnowledgeUploadSessionDetailResponse)
async def resolve_knowledge_upload_session_mappings(
    session_id: uuid.UUID,
    payload: KnowledgeUploadMappingsRequest,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> KnowledgeUploadSessionDetailResponse:
    return await service.apply_admin_session_mappings(
        session_id=session_id,
        mappings=payload.mappings,
        current_user=current_user,
    )


@router.patch(
    "/sessions/{session_id}/candidates/{candidate_id}",
    response_model=KnowledgeUploadCandidateResponse,
)
async def update_knowledge_upload_session_candidate(
    session_id: uuid.UUID,
    candidate_id: uuid.UUID,
    payload: KnowledgeUploadCandidateUpdateRequest,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> KnowledgeUploadCandidateResponse:
    return await service.update_admin_session_candidate(
        session_id=session_id,
        candidate_id=candidate_id,
        partner_id=payload.partner_id,
        cycle_month=payload.cycle_month,
        summary=payload.summary,
        status_value=payload.status,
    )


@router.post(
    "/sessions/{session_id}/candidates/{candidate_id}/dismiss",
    response_model=KnowledgeUploadCandidateResponse,
)
async def dismiss_knowledge_upload_session_candidate(
    session_id: uuid.UUID,
    candidate_id: uuid.UUID,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> KnowledgeUploadCandidateResponse:
    return await service.dismiss_admin_session_candidate(
        session_id=session_id,
        candidate_id=candidate_id,
    )


@router.post("/sessions/{session_id}/commit", response_model=KnowledgeUploadCommitResponse)
async def commit_knowledge_upload_session(
    session_id: uuid.UUID,
    payload: KnowledgeUploadCommitRequest,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> KnowledgeUploadCommitResponse:
    return await service.commit_admin_session(
        session_id=session_id,
        candidate_ids=payload.candidate_ids,
        current_user=current_admin,
    )


@router.get("/{upload_id}", response_model=KnowledgeUploadDetailResponse)
async def get_knowledge_upload(
    upload_id: uuid.UUID,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> KnowledgeUploadDetailResponse:
    return await service.get_admin_upload_detail(upload_id=upload_id)


@router.patch(
    "/{upload_id}/candidates/{candidate_id}",
    response_model=KnowledgeUploadCandidateResponse,
)
async def update_knowledge_upload_candidate(
    upload_id: uuid.UUID,
    candidate_id: uuid.UUID,
    payload: KnowledgeUploadCandidateUpdateRequest,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> KnowledgeUploadCandidateResponse:
    return await service.update_admin_candidate(
        upload_id=upload_id,
        candidate_id=candidate_id,
        partner_id=payload.partner_id,
        cycle_month=payload.cycle_month,
        summary=payload.summary,
        status_value=payload.status,
    )


@router.post(
    "/{upload_id}/candidates/{candidate_id}/dismiss",
    response_model=KnowledgeUploadCandidateResponse,
)
async def dismiss_knowledge_upload_candidate(
    upload_id: uuid.UUID,
    candidate_id: uuid.UUID,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> KnowledgeUploadCandidateResponse:
    return await service.dismiss_admin_candidate(
        upload_id=upload_id,
        candidate_id=candidate_id,
    )


@router.post("/{upload_id}/stage", response_model=KnowledgeUploadStageResponse)
async def stage_knowledge_upload_candidates(
    upload_id: uuid.UUID,
    payload: KnowledgeUploadStageRequest,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> KnowledgeUploadStageResponse:
    return await service.stage_admin_candidates(
        upload_id=upload_id,
        candidate_ids=payload.candidate_ids,
        current_user=current_admin,
    )
