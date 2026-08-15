import re
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from html import unescape
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.knowledge_upload import KnowledgeUploadAgent
from app.agents.knowledge_upload.agent import KnowledgeUploadAgentInput
from app.agents.rulebooks import RulebookLoader
from app.core.config import Settings
from app.db.models.knowledge_upload import (
    KnowledgeUpload,
    KnowledgeUploadCandidate,
    KnowledgeUploadCandidateReviewStatus,
    KnowledgeUploadCandidateStatus,
    KnowledgeUploadScope,
    KnowledgeUploadSession,
    KnowledgeUploadSessionStatus,
    MemoryChunk,
)
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_update import (
    PartnerUpdate,
    PartnerUpdateSourceType,
    PartnerUpdateStatus,
)
from app.db.models.source_event import AgentRun, AgentRunStatus
from app.db.models.topic_update import EventTopic, EventTopicStatus, TopicUpdate, TopicUpdateStatus
from app.domains.identity.schemas import UserResponse
from app.domains.uploads.analyzer import build_knowledge_upload_candidates
from app.domains.uploads.schemas import (
    KnowledgeUploadCandidateResponse,
    KnowledgeUploadCommitResponse,
    KnowledgeUploadDetailResponse,
    KnowledgeUploadPartnerCommitSummary,
    KnowledgeUploadResponse,
    KnowledgeUploadSessionDetailResponse,
    KnowledgeUploadSessionResponse,
    KnowledgeUploadStageResponse,
    KnowledgeUploadTopicCommitSummary,
)
from app.domains.uploads.storage import readable_upload_file, store_upload_file

ADMIN_SESSION_EXTENSIONS = {".docx", ".pptx", ".xlsx"}
MAX_ADMIN_SESSION_FILES = 7


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

    async def get_admin_upload_detail(
        self,
        *,
        upload_id: uuid.UUID,
    ) -> KnowledgeUploadDetailResponse:
        upload, partner_name = await self._get_upload_with_partner_or_404(upload_id)
        candidates = await self._list_upload_candidates(upload_id)
        return KnowledgeUploadDetailResponse(
            upload=self._to_response(upload, partner_name),
            candidates=candidates,
        )

    async def create_admin_session(
        self,
        *,
        files: list[UploadFile],
        current_user: UserResponse,
    ) -> KnowledgeUploadSessionDetailResponse:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload at least one historical document.",
            )
        if len(files) > MAX_ADMIN_SESSION_FILES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Upload up to {MAX_ADMIN_SESSION_FILES} documents at a time.",
            )
        for file in files:
            suffix = Path(file.filename or "").suffix.lower()
            if suffix not in ADMIN_SESSION_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Upload DOCX, PPTX, or XLSX files for Knowledge Upload.",
                )

        rulebook = RulebookLoader().load("admin_knowledge_upload")
        now = datetime.now(UTC)
        session = KnowledgeUploadSession(
            uploaded_by=current_user.user_id,
            status=KnowledgeUploadSessionStatus.analyzing.value,
            summary="Upload received. Analysis is running.",
            rulebook_name=rulebook.name,
            rulebook_version=rulebook.trace_version,
            created_at=now,
            updated_at=now,
        )
        self.db.add(session)
        await self.db.flush()

        active_partners = await self._load_active_partners()
        active_event_topics = await self._load_active_event_topics()
        agent = KnowledgeUploadAgent()
        uploads: list[KnowledgeUpload] = []
        candidates: list[KnowledgeUploadCandidate] = []
        warnings: list[str] = []
        document_types: set[str] = set()
        cycles: set[date] = set()
        input_fingerprints: list[str] = []

        for file in files:
            upload = await self._create_upload_record(
                file=file,
                current_user=current_user,
                scope=KnowledgeUploadScope.admin_knowledge,
                partner_id=None,
                partner_name=None,
                title=None,
                description=None,
                session_id=session.session_id,
            )
            uploads.append(upload)
            with readable_upload_file(
                settings=self.settings,
                storage_backend=upload.storage_backend,
                storage_key=upload.storage_key,
                original_filename=upload.original_filename,
            ) as file_path:
                result = agent.analyze(
                    KnowledgeUploadAgentInput(
                        file_path=file_path,
                        original_filename=upload.original_filename,
                        upload_id=upload.upload_id,
                        session_id=session.session_id,
                        selected_partner_id=None,
                        active_partners=active_partners,
                        description=upload.description,
                        checksum_sha256=upload.checksum_sha256,
                    )
                )
            document_types.add(result.document_type)
            if result.inferred_cycle:
                cycles.add(result.inferred_cycle)
            warnings.extend(result.warnings)
            input_fingerprints.append(result.input_fingerprint)
            for candidate in result.candidates:
                self.db.add(candidate)
                candidates.append(candidate)

        self._auto_resolve_event_topics(candidates, active_event_topics)

        agent_run = AgentRun(
            run_type="knowledge_upload_extraction",
            model_name=None,
            rulebook_name=rulebook.name,
            rulebook_version=rulebook.trace_version,
            status=AgentRunStatus.succeeded.value,
            input_fingerprint=combined_fingerprint(input_fingerprints),
            output_json={
                "session_id": str(session.session_id),
                "uploads": len(uploads),
                "candidates": len(candidates),
                "extraction_mode": "deterministic_rulebook",
            },
            triggered_by=current_user.user_id,
            started_at=now,
            finished_at=datetime.now(UTC),
        )
        self.db.add(agent_run)
        await self.db.flush()

        inferred_cycle = next(iter(sorted(cycles)), None) if len(cycles) == 1 else None
        session.agent_run_id = agent_run.agent_run_id
        session.document_type = (
            next(iter(document_types)) if len(document_types) == 1 else "Mixed historical documents"
        )
        session.inferred_cycle = inferred_cycle
        session.cycle_confidence = "high" if inferred_cycle else "medium" if cycles else "low"
        session.partner_count = len(
            {candidate.partner_id for candidate in candidates if candidate.partner_id}
        )
        session.update_count = len(
            [
                candidate
                for candidate in candidates
                if candidate.review_status
                != KnowledgeUploadCandidateReviewStatus.likely_noise.value
            ]
        )
        session.unknown_name_count = len(unknown_labels_from_candidates(candidates))
        session.warnings_json = list(dict.fromkeys(warnings))[:25]
        session.status = KnowledgeUploadSessionStatus.ready_for_review.value
        session.summary = build_session_summary(session)
        session.updated_at = datetime.now(UTC)
        await self.db.commit()
        return await self.get_admin_session_detail(session_id=session.session_id)

    async def get_admin_session_detail(
        self,
        *,
        session_id: uuid.UUID,
    ) -> KnowledgeUploadSessionDetailResponse:
        session = await self._get_session_or_404(session_id)
        uploads = await self._list_session_uploads(session_id)
        candidates = await self._list_session_candidates(session_id)
        return KnowledgeUploadSessionDetailResponse(
            session=self._session_to_response(session),
            uploads=uploads,
            candidates=candidates,
            unknown_labels=unknown_labels_from_responses(candidates),
        )

    async def apply_admin_session_mappings(
        self,
        *,
        session_id: uuid.UUID,
        mappings: list,
        current_user: UserResponse,
    ) -> KnowledgeUploadSessionDetailResponse:
        await self._get_session_or_404(session_id)
        candidates = await self._load_session_candidate_models(session_id)
        candidates_by_label: dict[str, list[KnowledgeUploadCandidate]] = defaultdict(list)
        for candidate in candidates:
            label = clean_optional(candidate.raw_label)
            if label:
                candidates_by_label[label].append(candidate)

        for mapping in mappings:
            label = clean_required(mapping.raw_label, "Mapping label")
            action = mapping.action.strip().lower()
            rows = candidates_by_label.get(label, [])
            if action == "existing_partner":
                if mapping.partner_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Choose a partner for {label}.",
                    )
                await self._get_active_partner_name_or_404(mapping.partner_id)
                for candidate in rows:
                    candidate.partner_id = mapping.partner_id
                    candidate.topic_id = None
                    candidate.review_status = review_status_for_candidate(candidate)
                    candidate.parser_notes = parser_note_for_candidate(candidate)
                    candidate.updated_at = datetime.now(UTC)
            elif action == "existing_topic":
                topic_id = getattr(mapping, "topic_id", None)
                if topic_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Choose an Events/Topics label for {label}.",
                    )
                topic = await self._get_active_event_topic_or_404(topic_id)
                for candidate in rows:
                    candidate.topic_id = topic.topic_id
                    candidate.raw_label = topic.name
                    candidate.partner_id = None
                    candidate.review_status = (
                        KnowledgeUploadCandidateReviewStatus.topic_pending.value
                    )
                    candidate.status = KnowledgeUploadCandidateStatus.pending.value
                    candidate.parser_notes = "Mapped to existing Events/Topics label."
                    candidate.updated_at = datetime.now(UTC)
            elif action == "new_topic":
                topic = await self._get_or_create_event_topic(
                    getattr(mapping, "topic_name", None) or label,
                    created_by=current_user.user_id,
                )
                for candidate in rows:
                    candidate.topic_id = topic.topic_id
                    candidate.raw_label = topic.name
                    candidate.review_status = (
                        KnowledgeUploadCandidateReviewStatus.topic_pending.value
                    )
                    candidate.partner_id = None
                    candidate.status = KnowledgeUploadCandidateStatus.pending.value
                    candidate.parser_notes = "Will be stored in Events/Topics when committed."
                    candidate.updated_at = datetime.now(UTC)
            elif action in {"skip", "noise"}:
                for candidate in rows:
                    candidate.topic_id = None
                    candidate.review_status = (
                        KnowledgeUploadCandidateReviewStatus.likely_noise.value
                    )
                    candidate.status = KnowledgeUploadCandidateStatus.skipped.value
                    candidate.parser_notes = "Skipped during mapping resolution."
                    candidate.updated_at = datetime.now(UTC)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported mapping action {mapping.action!r}.",
                )

        session = await self._get_session_or_404(session_id)
        session.unknown_name_count = len(unknown_labels_from_candidates(candidates))
        session.summary = build_session_summary(session)
        session.updated_at = datetime.now(UTC)
        await self.db.commit()
        return await self.get_admin_session_detail(session_id=session_id)

    async def update_admin_session_candidate(
        self,
        *,
        session_id: uuid.UUID,
        candidate_id: uuid.UUID,
        partner_id: uuid.UUID | None,
        cycle_month: date | None,
        summary: str | None,
        status_value: KnowledgeUploadCandidateStatus | None,
    ) -> KnowledgeUploadCandidateResponse:
        candidate = await self._get_session_candidate_or_404(session_id, candidate_id)
        if candidate.status in {
            KnowledgeUploadCandidateStatus.committed.value,
            KnowledgeUploadCandidateStatus.skipped.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Committed or skipped candidates cannot be edited.",
            )

        partner_name = None
        if partner_id is not None:
            partner_name = await self._get_active_partner_name_or_404(partner_id)
        elif candidate.partner_id is not None:
            partner_name = await self._get_partner_name(candidate.partner_id)

        if summary is not None:
            candidate.summary = clean_required(summary, "Candidate summary")
        candidate.partner_id = partner_id
        if partner_id is not None:
            candidate.topic_id = None
        candidate.cycle_month = cycle_month
        candidate.review_status = review_status_for_candidate(candidate)
        candidate.parser_notes = parser_note_for_candidate(candidate)
        if status_value is not None:
            if (
                status_value == KnowledgeUploadCandidateStatus.approved
                and candidate.review_status
                not in {
                    KnowledgeUploadCandidateReviewStatus.ready.value,
                    KnowledgeUploadCandidateReviewStatus.topic_pending.value,
                }
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Resolve partner/topic and cycle before approving this candidate.",
                )
            candidate.status = status_value.value
        candidate.updated_at = datetime.now(UTC)
        await self.db.commit()
        topic_name = await self._get_event_topic_name(candidate.topic_id)
        return self._candidate_to_response(candidate, partner_name, topic_name)

    async def dismiss_admin_session_candidate(
        self,
        *,
        session_id: uuid.UUID,
        candidate_id: uuid.UUID,
    ) -> KnowledgeUploadCandidateResponse:
        candidate = await self._get_session_candidate_or_404(session_id, candidate_id)
        candidate.status = KnowledgeUploadCandidateStatus.dismissed.value
        candidate.updated_at = datetime.now(UTC)
        await self.db.commit()
        partner_name = await self._get_partner_name(candidate.partner_id)
        topic_name = await self._get_event_topic_name(candidate.topic_id)
        return self._candidate_to_response(candidate, partner_name, topic_name)

    async def commit_admin_session(
        self,
        *,
        session_id: uuid.UUID,
        candidate_ids: list[uuid.UUID],
        current_user: UserResponse,
    ) -> KnowledgeUploadCommitResponse:
        if not candidate_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select at least one update to commit.",
            )
        session = await self._get_session_or_404(session_id)
        upload_lookup = await self._session_upload_lookup(session_id)
        candidates = await self._load_session_candidate_models(session_id)
        candidate_map = {candidate.candidate_id: candidate for candidate in candidates}
        now = datetime.now(UTC)
        created_update_ids: list[uuid.UUID] = []
        created_topic_update_ids: list[uuid.UUID] = []
        skipped_count = 0

        for candidate_id in candidate_ids:
            candidate = candidate_map.get(candidate_id)
            if candidate is None:
                skipped_count += 1
                continue
            if not candidate_can_commit(candidate):
                candidate.status = KnowledgeUploadCandidateStatus.skipped.value
                candidate.updated_at = now
                skipped_count += 1
                continue

            if candidate.review_status == KnowledgeUploadCandidateReviewStatus.topic_pending.value:
                source_event_key = f"knowledge-upload-topic:{candidate.candidate_id}"
                existing_topic = await self._find_existing_topic_update(source_event_key)
                if existing_topic is not None:
                    candidate.status = KnowledgeUploadCandidateStatus.committed.value
                    candidate.committed_topic_update_id = existing_topic.topic_update_id
                    candidate.updated_at = now
                    skipped_count += 1
                    continue

                upload = upload_lookup.get(candidate.upload_id)
                event_topic = await self._event_topic_for_candidate(
                    candidate,
                    created_by=current_user.user_id,
                )
                topic_update = TopicUpdate(
                    topic_id=event_topic.topic_id,
                    topic_label=event_topic.name,
                    cycle_month=candidate.cycle_month,
                    title=build_update_title(candidate.summary),
                    summary=candidate.summary,
                    source_type=PartnerUpdateSourceType.file.value,
                    source_label=source_label_for_candidate(candidate, upload),
                    source_url=candidate.source_url,
                    source_event_key=source_event_key,
                    status=TopicUpdateStatus.approved.value,
                    created_by=current_user.user_id,
                    approved_by=current_user.user_id,
                    approved_at=now,
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(topic_update)
                await self.db.flush()
                candidate.status = KnowledgeUploadCandidateStatus.committed.value
                candidate.committed_topic_update_id = topic_update.topic_update_id
                candidate.updated_at = now
                created_topic_update_ids.append(topic_update.topic_update_id)
                continue

            source_event_key = f"knowledge-upload:{candidate.candidate_id}"
            existing = await self._find_existing_update(source_event_key)
            if existing is not None:
                candidate.status = KnowledgeUploadCandidateStatus.committed.value
                candidate.committed_update_id = existing.update_id
                candidate.updated_at = now
                skipped_count += 1
                continue

            upload = upload_lookup.get(candidate.upload_id)
            update = PartnerUpdate(
                partner_id=candidate.partner_id,
                cycle_month=candidate.cycle_month,
                title=build_update_title(candidate.summary),
                summary=candidate.summary,
                source_type=PartnerUpdateSourceType.file.value,
                source_label=source_label_for_candidate(candidate, upload),
                source_url=candidate.source_url,
                source_event_key=source_event_key,
                status=PartnerUpdateStatus.approved.value,
                created_by=current_user.user_id,
                approved_by=current_user.user_id,
                approved_at=now,
                created_at=now,
                updated_at=now,
            )
            self.db.add(update)
            await self.db.flush()
            self.db.add(
                MemoryChunk(
                    partner_id=candidate.partner_id,
                    update_id=update.update_id,
                    memory_text=html_to_plain_text(candidate.summary),
                    source_kind="knowledge_upload",
                    retrieval_enabled=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            candidate.status = KnowledgeUploadCandidateStatus.committed.value
            candidate.committed_update_id = update.update_id
            candidate.updated_at = now
            created_update_ids.append(update.update_id)

        session.status = KnowledgeUploadSessionStatus.committed.value
        session.updated_at = now
        await self.db.commit()
        return await self._commit_response(
            session_id=session_id,
            committed_count=len(created_update_ids) + len(created_topic_update_ids),
            skipped_count=skipped_count,
            created_update_ids=created_update_ids,
            created_topic_update_ids=created_topic_update_ids,
        )

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
        upload = await self._create_upload_record(
            file=file,
            current_user=current_user,
            scope=KnowledgeUploadScope.admin_knowledge,
            partner_id=partner_id,
            partner_name=partner_name,
            title=title,
            description=description,
            session_id=None,
        )
        for candidate in await self._analyze_admin_upload(upload):
            self.db.add(candidate)
        await self.db.commit()
        return self._to_response(upload, partner_name)

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
        upload = await self._create_upload_record(
            file=file,
            current_user=current_user,
            scope=KnowledgeUploadScope.contributor_partner_file,
            partner_id=partner_id,
            partner_name=partner_name,
            title=title,
            description=description,
            session_id=None,
        )
        await self.db.commit()
        return self._to_response(upload, partner_name)

    async def update_admin_candidate(
        self,
        *,
        upload_id: uuid.UUID,
        candidate_id: uuid.UUID,
        partner_id: uuid.UUID | None,
        cycle_month: date | None,
        summary: str | None,
        status_value: KnowledgeUploadCandidateStatus | None,
    ) -> KnowledgeUploadCandidateResponse:
        candidate = await self._get_candidate_or_404(upload_id, candidate_id)
        return (
            await self.update_admin_session_candidate(
                session_id=candidate.session_id or uuid.UUID(int=0),
                candidate_id=candidate_id,
                partner_id=partner_id,
                cycle_month=cycle_month,
                summary=summary,
                status_value=status_value,
            )
            if candidate.session_id
            else await self._update_legacy_candidate(
                candidate=candidate,
                partner_id=partner_id,
                cycle_month=cycle_month,
                summary=summary,
                status_value=status_value,
            )
        )

    async def dismiss_admin_candidate(
        self,
        *,
        upload_id: uuid.UUID,
        candidate_id: uuid.UUID,
    ) -> KnowledgeUploadCandidateResponse:
        candidate = await self._get_candidate_or_404(upload_id, candidate_id)
        candidate.status = KnowledgeUploadCandidateStatus.dismissed.value
        candidate.updated_at = datetime.now(UTC)
        await self.db.commit()
        partner_name = await self._get_partner_name(candidate.partner_id)
        topic_name = await self._get_event_topic_name(candidate.topic_id)
        return self._candidate_to_response(candidate, partner_name, topic_name)

    async def stage_admin_candidates(
        self,
        *,
        upload_id: uuid.UUID,
        candidate_ids: list[uuid.UUID],
        current_user: UserResponse,
    ) -> KnowledgeUploadStageResponse:
        upload, _ = await self._get_upload_with_partner_or_404(upload_id)
        if upload.session_id:
            response = await self.commit_admin_session(
                session_id=upload.session_id,
                candidate_ids=candidate_ids,
                current_user=current_user,
            )
            return KnowledgeUploadStageResponse(
                staged_count=response.committed_count,
                skipped_count=response.skipped_count,
                created_update_ids=response.created_update_ids,
            )
        candidates = await self._load_stageable_candidates(upload_id, candidate_ids)
        for candidate in candidates:
            candidate.status = KnowledgeUploadCandidateStatus.staged.value
        await self.db.commit()
        return KnowledgeUploadStageResponse(
            staged_count=len(candidates),
            skipped_count=max(0, len(candidate_ids) - len(candidates)),
            created_update_ids=[],
        )

    async def _update_legacy_candidate(
        self,
        *,
        candidate: KnowledgeUploadCandidate,
        partner_id: uuid.UUID | None,
        cycle_month: date | None,
        summary: str | None,
        status_value: KnowledgeUploadCandidateStatus | None,
    ) -> KnowledgeUploadCandidateResponse:
        partner_name = None
        if partner_id is not None:
            partner_name = await self._get_active_partner_name_or_404(partner_id)
        elif candidate.partner_id is not None:
            partner_name = await self._get_partner_name(candidate.partner_id)
        if summary is not None:
            candidate.summary = clean_required(summary, "Candidate summary")
        candidate.partner_id = partner_id
        if partner_id is not None:
            candidate.topic_id = None
        candidate.cycle_month = cycle_month
        candidate.review_status = review_status_for_candidate(candidate)
        if status_value is not None:
            candidate.status = status_value.value
        candidate.parser_notes = parser_note_for_candidate(candidate)
        candidate.updated_at = datetime.now(UTC)
        await self.db.commit()
        topic_name = await self._get_event_topic_name(candidate.topic_id)
        return self._candidate_to_response(candidate, partner_name, topic_name)

    async def _create_upload_record(
        self,
        *,
        file: UploadFile,
        current_user: UserResponse,
        scope: KnowledgeUploadScope,
        partner_id: uuid.UUID | None,
        partner_name: str | None,
        title: str | None,
        description: str | None,
        session_id: uuid.UUID | None,
    ) -> KnowledgeUpload:
        upload_id = uuid.uuid4()
        stored_file = await store_upload_file(
            upload_id=upload_id,
            file=file,
            settings=self.settings,
        )
        now = datetime.now(UTC)
        upload = KnowledgeUpload(
            upload_id=upload_id,
            session_id=session_id,
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
        await self.db.flush()
        return upload

    async def _list(self, statement) -> list[KnowledgeUploadResponse]:
        result = await self.db.execute(statement)
        return [self._to_response(upload, partner_name) for upload, partner_name in result.all()]

    def _base_list_statement(self) -> Select:
        return (
            select(KnowledgeUpload, Partner.name)
            .outerjoin(Partner, Partner.partner_id == KnowledgeUpload.partner_id)
            .order_by(KnowledgeUpload.created_at.desc(), KnowledgeUpload.original_filename.asc())
        )

    async def _get_session_or_404(self, session_id: uuid.UUID) -> KnowledgeUploadSession:
        result = await self.db.execute(
            select(KnowledgeUploadSession).where(KnowledgeUploadSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge upload session not found.",
            )
        return session

    async def _get_upload_with_partner_or_404(
        self,
        upload_id: uuid.UUID,
    ) -> tuple[KnowledgeUpload, str | None]:
        result = await self.db.execute(
            self._base_list_statement().where(KnowledgeUpload.upload_id == upload_id)
        )
        row = result.first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge upload not found.",
            )
        upload, partner_name = row
        return upload, partner_name

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

    async def _get_partner_name(self, partner_id: uuid.UUID | None) -> str | None:
        if partner_id is None:
            return None
        result = await self.db.execute(select(Partner.name).where(Partner.partner_id == partner_id))
        return result.scalar_one_or_none()

    async def _load_active_partners(self) -> list[Partner]:
        result = await self.db.execute(
            select(Partner)
            .where(Partner.status == PartnerStatus.active.value)
            .order_by(Partner.name.asc())
        )
        return list(result.scalars().all())

    async def _load_active_event_topics(self) -> list[EventTopic]:
        result = await self.db.execute(
            select(EventTopic)
            .where(EventTopic.status == EventTopicStatus.active.value)
            .order_by(EventTopic.name.asc())
        )
        return list(result.scalars().all())

    async def _get_active_event_topic_or_404(self, topic_id: uuid.UUID) -> EventTopic:
        result = await self.db.execute(
            select(EventTopic)
            .where(EventTopic.topic_id == topic_id)
            .where(EventTopic.status == EventTopicStatus.active.value)
        )
        topic = result.scalar_one_or_none()
        if topic is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Events/Topics label not found.",
            )
        return topic

    async def _get_event_topic_name(self, topic_id: uuid.UUID | None) -> str | None:
        if topic_id is None:
            return None
        result = await self.db.execute(
            select(EventTopic.name).where(EventTopic.topic_id == topic_id)
        )
        return result.scalar_one_or_none()

    async def _get_or_create_event_topic(
        self,
        name: str,
        *,
        created_by: uuid.UUID | None,
    ) -> EventTopic:
        cleaned = clean_required(name, "Events/Topics label")[:160]
        normalized = normalize_event_topic_name(cleaned)
        result = await self.db.execute(
            select(EventTopic).where(EventTopic.normalized_name == normalized)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            if existing.status != EventTopicStatus.active.value:
                existing.status = EventTopicStatus.active.value
                existing.updated_at = datetime.now(UTC)
            return existing
        now = datetime.now(UTC)
        topic = EventTopic(
            name=cleaned,
            normalized_name=normalized,
            status=EventTopicStatus.active.value,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.db.add(topic)
        await self.db.flush()
        return topic

    async def _event_topic_for_candidate(
        self,
        candidate: KnowledgeUploadCandidate,
        *,
        created_by: uuid.UUID | None,
    ) -> EventTopic:
        if candidate.topic_id is not None:
            return await self._get_active_event_topic_or_404(candidate.topic_id)
        return await self._get_or_create_event_topic(
            topic_label_for_candidate(candidate),
            created_by=created_by,
        )

    def _auto_resolve_event_topics(
        self,
        candidates: list[KnowledgeUploadCandidate],
        active_event_topics: list[EventTopic],
    ) -> None:
        topic_lookup = {
            normalize_event_topic_name(topic.name): topic
            for topic in active_event_topics
            if topic.status == EventTopicStatus.active.value
        }
        for candidate in candidates:
            if (
                candidate.partner_id is not None
                or candidate.review_status
                != KnowledgeUploadCandidateReviewStatus.needs_mapping.value
                or candidate.status != KnowledgeUploadCandidateStatus.pending.value
            ):
                continue
            raw_label = clean_optional(candidate.raw_label)
            if raw_label is None:
                continue
            topic = topic_lookup.get(normalize_event_topic_name(raw_label))
            if topic is None:
                continue
            candidate.topic_id = topic.topic_id
            candidate.raw_label = topic.name
            candidate.review_status = KnowledgeUploadCandidateReviewStatus.topic_pending.value
            candidate.parser_notes = "Matched existing Events/Topics label."

    async def _analyze_admin_upload(
        self,
        upload: KnowledgeUpload,
    ) -> list[KnowledgeUploadCandidate]:
        with readable_upload_file(
            settings=self.settings,
            storage_backend=upload.storage_backend,
            storage_key=upload.storage_key,
            original_filename=upload.original_filename,
        ) as file_path:
            if not file_path.is_file():
                return []
            return build_knowledge_upload_candidates(
                file_path=file_path,
                original_filename=upload.original_filename,
                upload_id=upload.upload_id,
                selected_partner_id=upload.partner_id,
                active_partners=await self._load_active_partners(),
                description=upload.description,
            )

    async def _list_upload_candidates(
        self,
        upload_id: uuid.UUID,
    ) -> list[KnowledgeUploadCandidateResponse]:
        result = await self.db.execute(
            select(KnowledgeUploadCandidate, Partner.name, EventTopic.name)
            .outerjoin(Partner, Partner.partner_id == KnowledgeUploadCandidate.partner_id)
            .outerjoin(EventTopic, EventTopic.topic_id == KnowledgeUploadCandidate.topic_id)
            .where(KnowledgeUploadCandidate.upload_id == upload_id)
            .order_by(
                KnowledgeUploadCandidate.created_at.asc(),
                KnowledgeUploadCandidate.candidate_id.asc(),
            )
        )
        return [
            self._candidate_to_response(candidate, partner_name, topic_name)
            for candidate, partner_name, topic_name in result.all()
        ]

    async def _list_session_uploads(
        self,
        session_id: uuid.UUID,
    ) -> list[KnowledgeUploadResponse]:
        return await self._list(
            self._base_list_statement().where(KnowledgeUpload.session_id == session_id)
        )

    async def _session_upload_lookup(
        self,
        session_id: uuid.UUID,
    ) -> dict[uuid.UUID, KnowledgeUpload]:
        result = await self.db.execute(
            select(KnowledgeUpload).where(KnowledgeUpload.session_id == session_id)
        )
        return {upload.upload_id: upload for upload in result.scalars().all()}

    async def _list_session_candidates(
        self,
        session_id: uuid.UUID,
    ) -> list[KnowledgeUploadCandidateResponse]:
        result = await self.db.execute(
            select(KnowledgeUploadCandidate, Partner.name, EventTopic.name)
            .outerjoin(Partner, Partner.partner_id == KnowledgeUploadCandidate.partner_id)
            .outerjoin(EventTopic, EventTopic.topic_id == KnowledgeUploadCandidate.topic_id)
            .where(KnowledgeUploadCandidate.session_id == session_id)
            .order_by(
                Partner.name.asc().nullslast(),
                EventTopic.name.asc().nullslast(),
                KnowledgeUploadCandidate.created_at.asc(),
                KnowledgeUploadCandidate.candidate_id.asc(),
            )
        )
        return [
            self._candidate_to_response(candidate, partner_name, topic_name)
            for candidate, partner_name, topic_name in result.all()
        ]

    async def _load_session_candidate_models(
        self,
        session_id: uuid.UUID,
    ) -> list[KnowledgeUploadCandidate]:
        result = await self.db.execute(
            select(KnowledgeUploadCandidate).where(
                KnowledgeUploadCandidate.session_id == session_id
            )
        )
        return list(result.scalars().all())

    async def _get_candidate_or_404(
        self,
        upload_id: uuid.UUID,
        candidate_id: uuid.UUID,
    ) -> KnowledgeUploadCandidate:
        result = await self.db.execute(
            select(KnowledgeUploadCandidate)
            .where(KnowledgeUploadCandidate.upload_id == upload_id)
            .where(KnowledgeUploadCandidate.candidate_id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge candidate not found.",
            )
        return candidate

    async def _get_session_candidate_or_404(
        self,
        session_id: uuid.UUID,
        candidate_id: uuid.UUID,
    ) -> KnowledgeUploadCandidate:
        result = await self.db.execute(
            select(KnowledgeUploadCandidate)
            .where(KnowledgeUploadCandidate.session_id == session_id)
            .where(KnowledgeUploadCandidate.candidate_id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge candidate not found.",
            )
        return candidate

    async def _load_stageable_candidates(
        self,
        upload_id: uuid.UUID,
        candidate_ids: list[uuid.UUID],
    ) -> list[KnowledgeUploadCandidate]:
        result = await self.db.execute(
            select(KnowledgeUploadCandidate)
            .where(KnowledgeUploadCandidate.upload_id == upload_id)
            .where(KnowledgeUploadCandidate.candidate_id.in_(candidate_ids))
            .where(KnowledgeUploadCandidate.status == KnowledgeUploadCandidateStatus.pending.value)
        )
        return list(result.scalars().all())

    async def _find_existing_update(self, source_event_key: str) -> PartnerUpdate | None:
        result = await self.db.execute(
            select(PartnerUpdate).where(PartnerUpdate.source_event_key == source_event_key)
        )
        return result.scalar_one_or_none()

    async def _find_existing_topic_update(self, source_event_key: str) -> TopicUpdate | None:
        result = await self.db.execute(
            select(TopicUpdate).where(TopicUpdate.source_event_key == source_event_key)
        )
        return result.scalar_one_or_none()

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

    async def _commit_response(
        self,
        *,
        session_id: uuid.UUID,
        committed_count: int,
        skipped_count: int,
        created_update_ids: list[uuid.UUID],
        created_topic_update_ids: list[uuid.UUID],
    ) -> KnowledgeUploadCommitResponse:
        detail = await self.get_admin_session_detail(session_id=session_id)
        grouped: dict[tuple[uuid.UUID, str], int] = defaultdict(int)
        topic_grouped: dict[str, int] = defaultdict(int)
        for candidate in detail.candidates:
            if (
                candidate.status == KnowledgeUploadCandidateStatus.committed
                and candidate.partner_id
                and candidate.partner_name
            ):
                grouped[(candidate.partner_id, candidate.partner_name)] += 1
            elif (
                candidate.status == KnowledgeUploadCandidateStatus.committed
                and candidate.committed_topic_update_id
            ):
                topic_grouped[topic_label_for_response(candidate)] += 1
        sorted_groups = sorted(grouped.items(), key=lambda item: item[0][1])
        sorted_topic_groups = sorted(topic_grouped.items(), key=lambda item: item[0])
        return KnowledgeUploadCommitResponse(
            session=detail.session,
            committed_count=committed_count,
            skipped_count=skipped_count,
            created_update_ids=created_update_ids,
            created_topic_update_ids=created_topic_update_ids,
            partner_summaries=[
                KnowledgeUploadPartnerCommitSummary(
                    partner_id=partner_id,
                    partner_name=partner_name,
                    updates_approved=count,
                    status="Ready",
                )
                for (partner_id, partner_name), count in sorted_groups
            ],
            topic_summaries=[
                KnowledgeUploadTopicCommitSummary(
                    topic_label=topic_label,
                    updates_approved=count,
                    status="Ready",
                )
                for topic_label, count in sorted_topic_groups
            ],
        )

    def _to_response(
        self,
        upload: KnowledgeUpload,
        partner_name: str | None,
    ) -> KnowledgeUploadResponse:
        return KnowledgeUploadResponse(
            upload_id=upload.upload_id,
            session_id=upload.session_id,
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

    def _session_to_response(
        self,
        session: KnowledgeUploadSession,
    ) -> KnowledgeUploadSessionResponse:
        return KnowledgeUploadSessionResponse(
            session_id=session.session_id,
            status=KnowledgeUploadSessionStatus(session.status),
            document_type=session.document_type,
            inferred_cycle=session.inferred_cycle,
            cycle_confidence=session.cycle_confidence,
            summary=session.summary,
            partner_count=session.partner_count,
            update_count=session.update_count,
            unknown_name_count=session.unknown_name_count,
            warnings=session.warnings_json or [],
            rulebook_name=session.rulebook_name,
            rulebook_version=session.rulebook_version,
            agent_run_id=session.agent_run_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    def _candidate_to_response(
        self,
        candidate: KnowledgeUploadCandidate,
        partner_name: str | None,
        topic_name: str | None = None,
    ) -> KnowledgeUploadCandidateResponse:
        return KnowledgeUploadCandidateResponse(
            candidate_id=candidate.candidate_id,
            session_id=candidate.session_id,
            upload_id=candidate.upload_id,
            partner_id=candidate.partner_id,
            partner_name=partner_name,
            topic_id=candidate.topic_id,
            topic_name=topic_name,
            cycle_month=candidate.cycle_month,
            raw_label=candidate.raw_label,
            summary=candidate.summary,
            evidence_snippet=candidate.evidence_snippet,
            section_label=candidate.section_label,
            source_filename=candidate.source_filename,
            source_location=candidate.source_location,
            source_url=candidate.source_url,
            confidence=candidate.confidence,
            review_status=KnowledgeUploadCandidateReviewStatus(candidate.review_status),
            status=KnowledgeUploadCandidateStatus(candidate.status),
            parser_notes=candidate.parser_notes,
            committed_update_id=candidate.committed_update_id,
            committed_topic_update_id=candidate.committed_topic_update_id,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
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


def clean_required(value: str | None, label: str) -> str:
    cleaned = clean_optional(value)
    if cleaned is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} is required.",
        )
    return cleaned


def build_update_title(summary: str) -> str:
    plain_summary = html_to_plain_text(summary)
    lines = plain_summary.strip().splitlines()
    first_line = lines[0] if lines else ""
    first_sentence = first_line.split(". ")[0].strip()
    return (first_sentence or "Knowledge upload update")[:300]


def html_to_plain_text(value: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", value)
    text = re.sub(r"(?i)</(?:p|li|div|h[1-6])>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    lines = [normalize_spacing(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def normalize_spacing(value: str) -> str:
    return " ".join(value.split())


def normalize_event_topic_name(value: str) -> str:
    return normalize_spacing(value).lower()[:180]


def build_session_summary(session: KnowledgeUploadSession) -> str:
    cycle = display_cycle(session.inferred_cycle)
    unknown = f"{session.unknown_name_count} unknown name"
    if session.unknown_name_count != 1:
        unknown += "s"
    return (
        f"I think this upload contains {session.document_type or 'historical partner knowledge'} "
        f"for {cycle}. I found {session.partner_count} configured partner"
        f"{'' if session.partner_count == 1 else 's'} and {session.update_count} updates. "
        f"{unknown}."
    )


def display_cycle(value: date | None) -> str:
    if value is None:
        return "the selected reporting period"
    return value.strftime("%b-%Y")


def review_status_for_candidate(candidate: KnowledgeUploadCandidate) -> str:
    if candidate.review_status in {
        KnowledgeUploadCandidateReviewStatus.likely_noise.value,
        KnowledgeUploadCandidateReviewStatus.duplicate.value,
        KnowledgeUploadCandidateReviewStatus.topic_pending.value,
    }:
        return candidate.review_status
    return (
        KnowledgeUploadCandidateReviewStatus.ready.value
        if candidate.partner_id is not None and candidate.cycle_month is not None
        else KnowledgeUploadCandidateReviewStatus.needs_mapping.value
    )


def parser_note_for_candidate(candidate: KnowledgeUploadCandidate) -> str | None:
    if candidate.review_status == KnowledgeUploadCandidateReviewStatus.ready.value:
        return None
    if candidate.review_status == KnowledgeUploadCandidateReviewStatus.likely_noise.value:
        return "Skipped as non-partner knowledge."
    if candidate.review_status == KnowledgeUploadCandidateReviewStatus.topic_pending.value:
        return "Will be stored in Events/Topics when committed."
    missing = []
    if candidate.partner_id is None:
        missing.append("partner")
    if candidate.cycle_month is None:
        missing.append("cycle")
    return f"Needs {' and '.join(missing)} before commit." if missing else None


def unknown_labels_from_candidates(candidates: list[KnowledgeUploadCandidate]) -> list[str]:
    labels = {
        candidate.raw_label
        for candidate in candidates
        if candidate.partner_id is None
        and candidate.status == KnowledgeUploadCandidateStatus.pending.value
        and candidate.review_status == KnowledgeUploadCandidateReviewStatus.needs_mapping.value
        and clean_optional(candidate.raw_label)
    }
    return sorted(str(label) for label in labels)


def unknown_labels_from_responses(candidates: list[KnowledgeUploadCandidateResponse]) -> list[str]:
    labels = {
        candidate.raw_label
        for candidate in candidates
        if candidate.partner_id is None
        and candidate.status == KnowledgeUploadCandidateStatus.pending
        and candidate.review_status == KnowledgeUploadCandidateReviewStatus.needs_mapping
        and clean_optional(candidate.raw_label)
    }
    return sorted(str(label) for label in labels)


def combined_fingerprint(values: list[str]) -> str | None:
    if not values:
        return None
    return "|".join(sorted(values))[:128]


def candidate_can_commit(candidate: KnowledgeUploadCandidate) -> bool:
    if (
        candidate.review_status == KnowledgeUploadCandidateReviewStatus.topic_pending.value
        and candidate.cycle_month is not None
        and candidate.status
        in {
            KnowledgeUploadCandidateStatus.pending.value,
            KnowledgeUploadCandidateStatus.approved.value,
        }
    ):
        return True
    return (
        candidate.partner_id is not None
        and candidate.cycle_month is not None
        and candidate.review_status == KnowledgeUploadCandidateReviewStatus.ready.value
        and candidate.status
        in {
            KnowledgeUploadCandidateStatus.pending.value,
            KnowledgeUploadCandidateStatus.approved.value,
        }
    )


def source_label_for_candidate(
    candidate: KnowledgeUploadCandidate,
    upload: KnowledgeUpload | None,
) -> str:
    if candidate.source_filename:
        return candidate.source_filename[:240]
    if upload:
        return (upload.title or upload.original_filename)[:240]
    return "Knowledge Upload"


def topic_label_for_candidate(candidate: KnowledgeUploadCandidate) -> str:
    label = clean_optional(candidate.raw_label) or clean_optional(candidate.section_label)
    return (label or "Events/Topics")[:160]


def topic_label_for_response(candidate: KnowledgeUploadCandidateResponse) -> str:
    label = (
        clean_optional(candidate.topic_name)
        or clean_optional(candidate.raw_label)
        or clean_optional(candidate.section_label)
    )
    return (label or "Events/Topics")[:160]
