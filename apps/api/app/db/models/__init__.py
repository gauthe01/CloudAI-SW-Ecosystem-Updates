"""SQLAlchemy model registry."""

from app.db.models.account_access_request import (
    AccountAccessRequest,
    AccountAccessRequestStatus,
)
from app.db.models.connected_source import (
    ConnectedSource,
    ConnectedSourceConfluencePage,
    ConnectedSourceGitHubTarget,
    ConnectedSourceJiraIssue,
    ConnectedSourceSharePointFile,
    ConnectedSourceSlackChannel,
    ConnectedSourceStatus,
    ConnectedSourceType,
)
from app.db.models.identity import (
    RoleType,
    User,
    UserLocalCredential,
    UserRoleAssignment,
    UserSession,
)
from app.db.models.integration import (
    Integration,
    IntegrationSecret,
    IntegrationStatus,
    IntegrationTestRun,
    IntegrationTestStatus,
    IntegrationType,
)
from app.db.models.knowledge_upload import (
    KnowledgeUpload,
    KnowledgeUploadCandidate,
    KnowledgeUploadCandidateReviewStatus,
    KnowledgeUploadCandidateStatus,
    KnowledgeUploadProcessingStatus,
    KnowledgeUploadScope,
    KnowledgeUploadSession,
    KnowledgeUploadSessionStatus,
    MemoryChunk,
)
from app.db.models.partner import (
    Partner,
    PartnerContributorAssignment,
    PartnerStatus,
)
from app.db.models.partner_metadata import (
    PartnerHealthStatus,
    PartnerMetadataRisk,
    PartnerMetadataSnapshot,
    PartnerResourceLink,
    ResourceLinkSourceKind,
)
from app.db.models.partner_update import (
    PartnerUpdate,
    PartnerUpdateSourceType,
    PartnerUpdateStatus,
)
from app.db.models.source_event import (
    AgentRun,
    AgentRunStatus,
    AgentRunType,
    SourceEvent,
    SourceEventStatus,
    SourcePayload,
    SourcePayloadRetentionPolicy,
)
from app.db.models.source_sync import SourceSyncRun, SourceSyncRunStatus, SourceSyncState
from app.db.models.storage_object import StorageObject, StorageObjectSourceKind
from app.db.models.topic_update import TopicUpdate, TopicUpdateStatus

__all__ = [
    "AccountAccessRequest",
    "AccountAccessRequestStatus",
    "ConnectedSource",
    "ConnectedSourceConfluencePage",
    "ConnectedSourceGitHubTarget",
    "ConnectedSourceJiraIssue",
    "ConnectedSourceSharePointFile",
    "ConnectedSourceSlackChannel",
    "ConnectedSourceStatus",
    "ConnectedSourceType",
    "AgentRun",
    "AgentRunStatus",
    "AgentRunType",
    "Integration",
    "IntegrationSecret",
    "IntegrationStatus",
    "IntegrationTestRun",
    "IntegrationTestStatus",
    "IntegrationType",
    "Partner",
    "PartnerContributorAssignment",
    "PartnerHealthStatus",
    "KnowledgeUpload",
    "KnowledgeUploadCandidate",
    "KnowledgeUploadCandidateReviewStatus",
    "KnowledgeUploadCandidateStatus",
    "KnowledgeUploadProcessingStatus",
    "KnowledgeUploadSession",
    "KnowledgeUploadSessionStatus",
    "KnowledgeUploadScope",
    "MemoryChunk",
    "PartnerMetadataRisk",
    "PartnerMetadataSnapshot",
    "PartnerResourceLink",
    "PartnerStatus",
    "PartnerUpdate",
    "PartnerUpdateSourceType",
    "PartnerUpdateStatus",
    "ResourceLinkSourceKind",
    "RoleType",
    "SourceEvent",
    "SourceEventStatus",
    "SourcePayload",
    "SourcePayloadRetentionPolicy",
    "SourceSyncRun",
    "SourceSyncRunStatus",
    "SourceSyncState",
    "StorageObject",
    "StorageObjectSourceKind",
    "TopicUpdate",
    "TopicUpdateStatus",
    "User",
    "UserLocalCredential",
    "UserRoleAssignment",
    "UserSession",
]
