import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.db.models.knowledge_upload import (
    KnowledgeUploadCandidateReviewStatus,
    KnowledgeUploadCandidateStatus,
    KnowledgeUploadProcessingStatus,
    KnowledgeUploadScope,
    KnowledgeUploadSessionStatus,
)


class KnowledgeUploadResponse(BaseModel):
    upload_id: uuid.UUID
    session_id: uuid.UUID | None = None
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


class KnowledgeUploadCandidateResponse(BaseModel):
    candidate_id: uuid.UUID
    session_id: uuid.UUID | None
    upload_id: uuid.UUID
    partner_id: uuid.UUID | None
    partner_name: str | None
    cycle_month: date | None
    raw_label: str | None
    summary: str
    evidence_snippet: str | None
    section_label: str | None
    source_filename: str | None
    source_location: str | None
    source_url: str | None
    confidence: str
    review_status: KnowledgeUploadCandidateReviewStatus
    status: KnowledgeUploadCandidateStatus
    parser_notes: str | None
    committed_update_id: uuid.UUID | None
    committed_topic_update_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class KnowledgeUploadDetailResponse(BaseModel):
    upload: KnowledgeUploadResponse
    candidates: list[KnowledgeUploadCandidateResponse]


class KnowledgeUploadCandidateUpdateRequest(BaseModel):
    partner_id: uuid.UUID | None = None
    cycle_month: date | None = None
    summary: str | None = Field(default=None, max_length=20000)
    status: KnowledgeUploadCandidateStatus | None = None


class KnowledgeUploadStageRequest(BaseModel):
    candidate_ids: list[uuid.UUID]


class KnowledgeUploadStageResponse(BaseModel):
    staged_count: int
    skipped_count: int
    created_update_ids: list[uuid.UUID]


class KnowledgeUploadSessionResponse(BaseModel):
    session_id: uuid.UUID
    status: KnowledgeUploadSessionStatus
    document_type: str | None
    inferred_cycle: date | None
    cycle_confidence: str | None
    summary: str | None
    partner_count: int
    update_count: int
    unknown_name_count: int
    warnings: list[str]
    rulebook_name: str
    rulebook_version: str
    agent_run_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class KnowledgeUploadSessionDetailResponse(BaseModel):
    session: KnowledgeUploadSessionResponse
    uploads: list[KnowledgeUploadResponse]
    candidates: list[KnowledgeUploadCandidateResponse]
    unknown_labels: list[str]


class KnowledgeUploadMappingDecision(BaseModel):
    raw_label: str
    action: str
    partner_id: uuid.UUID | None = None


class KnowledgeUploadMappingsRequest(BaseModel):
    mappings: list[KnowledgeUploadMappingDecision]


class KnowledgeUploadCommitRequest(BaseModel):
    candidate_ids: list[uuid.UUID]


class KnowledgeUploadPartnerCommitSummary(BaseModel):
    partner_id: uuid.UUID
    partner_name: str
    updates_approved: int
    status: str


class KnowledgeUploadTopicCommitSummary(BaseModel):
    topic_label: str
    updates_approved: int
    status: str


class KnowledgeUploadCommitResponse(BaseModel):
    session: KnowledgeUploadSessionResponse
    committed_count: int
    skipped_count: int
    partner_summaries: list[KnowledgeUploadPartnerCommitSummary]
    topic_summaries: list[KnowledgeUploadTopicCommitSummary] = Field(default_factory=list)
    created_update_ids: list[uuid.UUID]
    created_topic_update_ids: list[uuid.UUID] = Field(default_factory=list)
