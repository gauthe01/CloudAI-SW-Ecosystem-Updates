import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse
from app.domains.uploads.schemas import KnowledgeUploadListResponse, KnowledgeUploadResponse
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
