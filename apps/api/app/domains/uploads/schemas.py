import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models.knowledge_upload import (
    KnowledgeUploadProcessingStatus,
    KnowledgeUploadScope,
)


class KnowledgeUploadResponse(BaseModel):
    upload_id: uuid.UUID
    partner_id: uuid.UUID | None
    partner_name: str | None
    scope: KnowledgeUploadScope
    title: str
    description: str | None
    original_filename: str
    content_type: str | None
    file_size_bytes: int
    checksum_sha256: str
    storage_backend: str
    processing_status: KnowledgeUploadProcessingStatus
    text_preview: str | None
    uploaded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class KnowledgeUploadListResponse(BaseModel):
    uploads: list[KnowledgeUploadResponse]
