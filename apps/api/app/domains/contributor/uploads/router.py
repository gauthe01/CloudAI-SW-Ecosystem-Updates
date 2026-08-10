import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse
from app.domains.uploads.schemas import KnowledgeUploadListResponse, KnowledgeUploadResponse
from app.domains.uploads.service import KnowledgeUploadService

router = APIRouter(
    prefix="/api/contributor/partners/{partner_id}/uploads",
    tags=["contributor-uploads"],
)


def get_knowledge_upload_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeUploadService:
    return KnowledgeUploadService(db, settings)


@router.get("", response_model=KnowledgeUploadListResponse)
async def list_partner_uploads(
    partner_id: uuid.UUID,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
) -> KnowledgeUploadListResponse:
    return KnowledgeUploadListResponse(
        uploads=await service.list_contributor_partner_uploads(
            partner_id=partner_id,
            current_user=current_user,
        )
    )


@router.post("", response_model=KnowledgeUploadResponse, status_code=status.HTTP_201_CREATED)
async def create_partner_upload(
    partner_id: uuid.UUID,
    service: Annotated[KnowledgeUploadService, Depends(get_knowledge_upload_service)],
    current_user: Annotated[UserResponse, Depends(require_roles(RoleType.contributor))],
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
) -> KnowledgeUploadResponse:
    return await service.create_contributor_partner_upload(
        partner_id=partner_id,
        file=file,
        current_user=current_user,
        title=title,
        description=description,
    )
