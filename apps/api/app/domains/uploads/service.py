import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.knowledge_upload import KnowledgeUpload, KnowledgeUploadScope
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.domains.identity.schemas import UserResponse
from app.domains.uploads.schemas import KnowledgeUploadResponse
from app.domains.uploads.storage import store_upload_file


class KnowledgeUploadService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def list_admin_uploads(
        self,
        *,
        partner_id: uuid.UUID | None = None,
    ) -> list[KnowledgeUploadResponse]:
        statement = self._base_list_statement()
        if partner_id:
            statement = statement.where(KnowledgeUpload.partner_id == partner_id)
        return await self._list(statement)

    async def list_contributor_partner_uploads(
        self,
        *,
        partner_id: uuid.UUID,
        current_user: UserResponse,
    ) -> list[KnowledgeUploadResponse]:
        await self._ensure_assigned_active_partner(partner_id, current_user)
        statement = (
            self._base_list_statement()
            .where(KnowledgeUpload.partner_id == partner_id)
            .where(KnowledgeUpload.scope == KnowledgeUploadScope.contributor_partner_file.value)
        )
        return await self._list(statement)

    async def create_admin_upload(
        self,
        *,
        file: UploadFile,
        current_user: UserResponse,
        partner_id: uuid.UUID | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> KnowledgeUploadResponse:
        partner_name = None
        if partner_id is not None:
            partner_name = await self._get_active_partner_name_or_404(partner_id)
        return await self._create_upload(
            file=file,
            current_user=current_user,
            scope=KnowledgeUploadScope.admin_knowledge,
            partner_id=partner_id,
            partner_name=partner_name,
            title=title,
            description=description,
        )

    async def create_contributor_partner_upload(
        self,
        *,
        partner_id: uuid.UUID,
        file: UploadFile,
        current_user: UserResponse,
        title: str | None = None,
        description: str | None = None,
    ) -> KnowledgeUploadResponse:
        partner_name = await self._ensure_assigned_active_partner(partner_id, current_user)
        return await self._create_upload(
            file=file,
            current_user=current_user,
            scope=KnowledgeUploadScope.contributor_partner_file,
            partner_id=partner_id,
            partner_name=partner_name,
            title=title,
            description=description,
        )

    async def _create_upload(
        self,
        *,
        file: UploadFile,
        current_user: UserResponse,
        scope: KnowledgeUploadScope,
        partner_id: uuid.UUID | None,
        partner_name: str | None,
        title: str | None,
        description: str | None,
    ) -> KnowledgeUploadResponse:
        upload_id = uuid.uuid4()
        stored_file = await store_upload_file(
            upload_id=upload_id,
            file=file,
            settings=self.settings,
        )
        now = datetime.now(UTC)
        upload = KnowledgeUpload(
            upload_id=upload_id,
            partner_id=partner_id,
            scope=scope.value,
            title=clean_title(title, stored_file.original_filename),
            description=clean_optional(description),
            original_filename=stored_file.original_filename,
            content_type=stored_file.content_type,
            file_size_bytes=stored_file.file_size_bytes,
            checksum_sha256=stored_file.checksum_sha256,
            storage_backend=stored_file.storage_backend,
            storage_key=stored_file.storage_key,
            processing_status=stored_file.processing_status.value,
            text_preview=stored_file.text_preview,
            uploaded_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(upload)
        await self.db.commit()
        return self._to_response(upload, partner_name)

    async def _list(self, statement) -> list[KnowledgeUploadResponse]:
        result = await self.db.execute(statement)
        return [self._to_response(upload, partner_name) for upload, partner_name in result.all()]

    def _base_list_statement(self) -> Select:
        return (
            select(KnowledgeUpload, Partner.name)
            .outerjoin(Partner, Partner.partner_id == KnowledgeUpload.partner_id)
            .order_by(KnowledgeUpload.created_at.desc(), KnowledgeUpload.original_filename.asc())
        )

    async def _get_active_partner_name_or_404(self, partner_id: uuid.UUID) -> str:
        statement = (
            select(Partner.name)
            .where(Partner.partner_id == partner_id)
            .where(Partner.status == PartnerStatus.active.value)
        )
        result = await self.db.execute(statement)
        partner_name = result.scalar_one_or_none()
        if partner_name is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partner not found.",
            )
        return partner_name

    async def _ensure_assigned_active_partner(
        self,
        partner_id: uuid.UUID,
        current_user: UserResponse,
    ) -> str:
        statement = (
            select(Partner.name)
            .join(
                PartnerContributorAssignment,
                PartnerContributorAssignment.partner_id == Partner.partner_id,
            )
            .where(Partner.partner_id == partner_id)
            .where(PartnerContributorAssignment.user_id == current_user.user_id)
            .where(Partner.status == PartnerStatus.active.value)
        )
        result = await self.db.execute(statement)
        partner_name = result.scalar_one_or_none()
        if partner_name is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Partner uploads are not assigned to this contributor.",
            )
        return partner_name

    def _to_response(
        self,
        upload: KnowledgeUpload,
        partner_name: str | None,
    ) -> KnowledgeUploadResponse:
        return KnowledgeUploadResponse(
            upload_id=upload.upload_id,
            partner_id=upload.partner_id,
            partner_name=partner_name,
            scope=KnowledgeUploadScope(upload.scope),
            title=upload.title,
            description=upload.description,
            original_filename=upload.original_filename,
            content_type=upload.content_type,
            file_size_bytes=upload.file_size_bytes,
            checksum_sha256=upload.checksum_sha256,
            storage_backend=upload.storage_backend,
            processing_status=upload.processing_status,
            text_preview=upload.text_preview,
            uploaded_by=upload.uploaded_by,
            created_at=upload.created_at,
            updated_at=upload.updated_at,
        )


def clean_title(value: str | None, fallback_filename: str) -> str:
    cleaned = value.strip() if value else ""
    if cleaned:
        return cleaned[:300]
    return fallback_filename[:300]


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
