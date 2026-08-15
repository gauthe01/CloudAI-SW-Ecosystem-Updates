import uuid
from datetime import date
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.identity import RoleType, User, UserRoleAssignment, UserSession
from app.db.models.knowledge_upload import (
    KnowledgeUpload,
    KnowledgeUploadCandidate,
    KnowledgeUploadCandidateStatus,
    KnowledgeUploadSession,
    MemoryChunk,
)
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.db.models.source_event import AgentRun
from app.db.models.topic_update import TopicUpdate, TopicUpdateStatus
from app.db.session import get_session_factory
from app.domains.identity.service import user_to_response
from app.domains.uploads import storage as upload_storage
from app.domains.uploads.analyzer import build_knowledge_upload_candidates, infer_cycle_month
from app.domains.uploads.service import KnowledgeUploadService


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.extra_args: dict[tuple[str, str], dict | None] = {}

    def upload_file(
        self,
        filename: str,
        bucket: str,
        key: str,
        ExtraArgs: dict | None = None,
    ) -> None:
        self.objects[(bucket, key)] = Path(filename).read_bytes()
        self.extra_args[(bucket, key)] = ExtraArgs

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        Path(filename).write_bytes(self.objects[(bucket, key)])


@pytest.mark.asyncio
async def test_knowledge_uploads_store_metadata_and_enforce_partner_assignment(tmp_path) -> None:
    admin_email = f"upload-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"upload-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Upload Partner {uuid.uuid4()}"
    unassigned_partner_name = f"Unassigned Upload Partner {uuid.uuid4()}"
    settings = get_settings().model_copy(update={"local_upload_storage_dir": str(tmp_path)})

    async with get_session_factory()() as session:
        await cleanup_test_records(
            session,
            [partner_name, unassigned_partner_name],
            [admin_email, contributor_email],
        )
        admin = User(email=admin_email, display_name="Upload Admin")
        admin.role_assignments = [UserRoleAssignment(role_type=RoleType.admin)]
        contributor = User(email=contributor_email, display_name="Upload Contributor")
        contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
        partner = Partner(
            name=partner_name,
            description="Upload partner",
            status=PartnerStatus.active.value,
        )
        unassigned_partner = Partner(
            name=unassigned_partner_name,
            description="Unassigned partner",
            status=PartnerStatus.active.value,
        )
        session.add_all([admin, contributor, partner, unassigned_partner])
        await session.flush()
        session.add(
            PartnerContributorAssignment(
                partner_id=partner.partner_id,
                user_id=contributor.user_id,
            )
        )
        await session.commit()

        service = KnowledgeUploadService(session, settings)
        admin_upload = await service.create_admin_upload(
            file=upload_file("admin-notes.txt", b"Admin knowledge upload notes"),
            current_user=user_to_response(admin),
            title="Admin notes",
            description="Global knowledge",
        )
        assert admin_upload.title == "Admin notes"
        assert admin_upload.partner_id is None
        assert admin_upload.scope == "admin_knowledge"
        assert admin_upload.processing_status == "parsed"
        assert admin_upload.text_preview == "Admin knowledge upload notes"
        assert admin_upload.file_size_bytes == 28

        mapped_upload = await service.create_admin_upload(
            file=upload_file(
                "sap-august-2026-notes.txt",
                (
                    b"SAP HANA Cloud published 3 training updates in August 2026.\n\n"
                    b"SAP HANA Cloud blocker cleared for partner review in August 2026."
                ),
            ),
            current_user=user_to_response(admin),
            partner_id=partner.partner_id,
            title="SAP August notes",
            description="August 2026 admin report",
        )
        detail = await service.get_admin_upload_detail(upload_id=mapped_upload.upload_id)
        assert len(detail.candidates) == 2
        assert {candidate.partner_id for candidate in detail.candidates} == {partner.partner_id}
        assert {candidate.cycle_month.isoformat() for candidate in detail.candidates} == {
            "2026-08-01"
        }

        stage_result = await service.stage_admin_candidates(
            upload_id=mapped_upload.upload_id,
            candidate_ids=[candidate.candidate_id for candidate in detail.candidates],
            current_user=user_to_response(admin),
        )
        assert stage_result.staged_count == 2
        assert stage_result.skipped_count == 0

        staged_detail = await service.get_admin_upload_detail(upload_id=mapped_upload.upload_id)
        assert {candidate.status for candidate in staged_detail.candidates} == {"staged"}

        contributor_upload = await service.create_contributor_partner_upload(
            partner_id=partner.partner_id,
            file=upload_file("partner-update.md", b"# Partner file\nImportant detail"),
            current_user=user_to_response(contributor),
        )
        assert contributor_upload.title == "partner-update.md"
        assert contributor_upload.partner_id == partner.partner_id
        assert contributor_upload.partner_name == partner_name
        assert contributor_upload.scope == "contributor_partner_file"
        assert contributor_upload.text_preview == "# Partner file\nImportant detail"

        contributor_uploads = await service.list_contributor_partner_uploads(
            partner_id=partner.partner_id,
            current_user=user_to_response(contributor),
        )
        assert [upload.upload_id for upload in contributor_uploads] == [
            contributor_upload.upload_id
        ]

        admin_uploads = await service.list_admin_uploads()
        assert {upload.upload_id for upload in admin_uploads} >= {
            admin_upload.upload_id,
            contributor_upload.upload_id,
        }

        with pytest.raises(HTTPException) as exc_info:
            await service.create_contributor_partner_upload(
                partner_id=unassigned_partner.partner_id,
                file=upload_file("blocked.txt", b"blocked"),
                current_user=user_to_response(contributor),
            )
        assert exc_info.value.status_code == 403

        with pytest.raises(HTTPException) as unsupported_exc:
            await service.create_admin_upload(
                file=upload_file("script.sh", b"echo unsafe"),
                current_user=user_to_response(admin),
            )
        assert unsupported_exc.value.status_code == 400

        await cleanup_test_records(
            session,
            [partner_name, unassigned_partner_name],
            [admin_email, contributor_email],
        )
        await session.commit()


@pytest.mark.asyncio
async def test_admin_knowledge_upload_session_commits_only_approved_memory(tmp_path) -> None:
    admin_email = f"session-upload-admin-{uuid.uuid4()}@example.com"
    partner_name = f"SessionPartner{uuid.uuid4().hex[:8]}"
    settings = get_settings().model_copy(update={"local_upload_storage_dir": str(tmp_path)})

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email])
        admin = User(email=admin_email, display_name="Session Upload Admin")
        admin.role_assignments = [UserRoleAssignment(role_type=RoleType.admin)]
        partner = Partner(
            name=partner_name,
            description="Session partner",
            status=PartnerStatus.active.value,
        )
        session.add_all([admin, partner])
        await session.commit()

        service = KnowledgeUploadService(session, settings)
        detail = await service.create_admin_session(
            files=[
                upload_file(
                    "Software EcosystemMonthly Status Report_July 24 2026.docx",
                    docx_bytes(
                        [
                            partner_name,
                            (
                                f"{partner_name} published AGI CPU certification updates "
                                "for July 2026."
                            ),
                            (
                                f"{partner_name} needs the hardware loaner agreement for "
                                "July 2026 qualification."
                            ),
                        ]
                    ),
                )
            ],
            current_user=user_to_response(admin),
        )

        assert detail.session.rulebook_name == "admin_knowledge_upload"
        assert detail.session.rulebook_version
        assert detail.session.document_type == "Software Ecosystem Monthly Status Report"
        assert detail.session.inferred_cycle == date(2026, 7, 1)
        assert detail.session.partner_count == 1
        assert detail.session.update_count == 2
        assert len(detail.candidates) == 2
        assert {candidate.status for candidate in detail.candidates} == {"pending"}

        before_updates = await session.scalars(
            select(PartnerUpdate).where(PartnerUpdate.partner_id == partner.partner_id)
        )
        before_memory = await session.scalars(
            select(MemoryChunk).where(MemoryChunk.partner_id == partner.partner_id)
        )
        assert list(before_updates) == []
        assert list(before_memory) == []

        approved = await service.update_admin_session_candidate(
            session_id=detail.session.session_id,
            candidate_id=detail.candidates[0].candidate_id,
            partner_id=detail.candidates[0].partner_id,
            cycle_month=detail.candidates[0].cycle_month,
            summary=detail.candidates[0].summary,
            status_value=KnowledgeUploadCandidateStatus.approved,
        )
        assert approved.status == KnowledgeUploadCandidateStatus.approved

        commit = await service.commit_admin_session(
            session_id=detail.session.session_id,
            candidate_ids=[approved.candidate_id],
            current_user=user_to_response(admin),
        )

        assert commit.committed_count == 1
        assert commit.skipped_count == 0
        assert commit.partner_summaries[0].partner_name == partner_name
        assert commit.partner_summaries[0].updates_approved == 1

        committed_updates = list(
            await session.scalars(
                select(PartnerUpdate).where(PartnerUpdate.partner_id == partner.partner_id)
            )
        )
        memory_chunks = list(
            await session.scalars(
                select(MemoryChunk).where(MemoryChunk.partner_id == partner.partner_id)
            )
        )
        assert len(committed_updates) == 1
        assert committed_updates[0].status == PartnerUpdateStatus.approved.value
        assert committed_updates[0].source_event_key == f"knowledge-upload:{approved.candidate_id}"
        assert len(memory_chunks) == 1
        assert memory_chunks[0].retrieval_enabled is True
        assert memory_chunks[0].update_id == committed_updates[0].update_id

        final_detail = await service.get_admin_session_detail(session_id=detail.session.session_id)
        statuses = {
            candidate.candidate_id: candidate.status for candidate in final_detail.candidates
        }
        assert statuses[approved.candidate_id] == KnowledgeUploadCandidateStatus.committed

        await cleanup_test_records(session, [partner_name], [admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_admin_knowledge_upload_session_reads_from_s3_storage(
    tmp_path,
    monkeypatch,
) -> None:
    admin_email = f"s3-upload-admin-{uuid.uuid4()}@example.com"
    partner_name = f"S3Partner{uuid.uuid4().hex[:8]}"
    fake_s3 = FakeS3Client()
    monkeypatch.setattr(upload_storage, "get_s3_client", lambda settings: fake_s3)
    settings = get_settings().model_copy(
        update={
            "file_storage_backend": "s3",
            "s3_bucket": "knowledge-upload-test-bucket",
            "local_upload_storage_dir": str(tmp_path),
        }
    )

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email])
        admin = User(email=admin_email, display_name="S3 Upload Admin")
        admin.role_assignments = [UserRoleAssignment(role_type=RoleType.admin)]
        partner = Partner(
            name=partner_name,
            description="S3 session partner",
            status=PartnerStatus.active.value,
        )
        session.add_all([admin, partner])
        await session.commit()

        service = KnowledgeUploadService(session, settings)
        detail = await service.create_admin_session(
            files=[
                upload_file(
                    "Software Ecosystem Monthly Status Report_Aug 2026.docx",
                    docx_bytes(
                        [
                            partner_name,
                            f"{partner_name} confirmed S3-backed upload parsing in Aug 2026.",
                        ]
                    ),
                )
            ],
            current_user=user_to_response(admin),
        )

        upload = detail.uploads[0]
        assert upload.storage_backend == "s3"
        assert len(fake_s3.objects) == 1
        [(bucket, storage_key)] = list(fake_s3.objects)
        assert bucket == settings.s3_bucket
        assert storage_key.startswith("uploads/")
        assert not (Path(settings.local_upload_storage_dir) / storage_key).exists()
        assert len(detail.candidates) == 1
        assert detail.candidates[0].partner_id == partner.partner_id
        assert detail.candidates[0].cycle_month == date(2026, 8, 1)
        assert "S3-backed upload parsing" in detail.candidates[0].summary

        await cleanup_test_records(session, [partner_name], [admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_admin_knowledge_upload_session_commits_events_topics(tmp_path) -> None:
    admin_email = f"topic-upload-admin-{uuid.uuid4()}@example.com"
    partner_name = f"TopicPartner{uuid.uuid4().hex[:8]}"
    settings = get_settings().model_copy(update={"local_upload_storage_dir": str(tmp_path)})

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email])
        admin = User(email=admin_email, display_name="Topic Upload Admin")
        admin.role_assignments = [UserRoleAssignment(role_type=RoleType.admin)]
        partner = Partner(
            name=partner_name,
            description="Partner present so the report has configured partner context",
            status=PartnerStatus.active.value,
        )
        session.add_all([admin, partner])
        await session.commit()

        service = KnowledgeUploadService(session, settings)
        detail = await service.create_admin_session(
            files=[
                upload_file(
                    "Software Ecosystem Monthly Status Report_Feb 28 2026.docx",
                    docx_list_bytes(
                        [
                            ("Ecosystem Projects:", 1, None),
                            ("Ecosystem Dashboard", 0, None, "16"),
                            ("500+ recommended packages", 1, None, "16"),
                        ]
                    ),
                )
            ],
            current_user=user_to_response(admin),
        )

        assert detail.unknown_labels == ["Ecosystem Projects"]
        mapped = await service.apply_admin_session_mappings(
            session_id=detail.session.session_id,
            mappings=[
                type(
                    "Mapping",
                    (),
                    {
                        "raw_label": "Ecosystem Projects",
                        "action": "new_topic",
                        "partner_id": None,
                    },
                )()
            ],
        )
        topic_candidate = mapped.candidates[0]
        assert topic_candidate.partner_id is None
        assert topic_candidate.review_status == "topic_pending"
        assert "Events/Topics" in (topic_candidate.parser_notes or "")

        approved = await service.update_admin_session_candidate(
            session_id=detail.session.session_id,
            candidate_id=topic_candidate.candidate_id,
            partner_id=None,
            cycle_month=topic_candidate.cycle_month,
            summary=topic_candidate.summary,
            status_value=KnowledgeUploadCandidateStatus.approved,
        )
        commit = await service.commit_admin_session(
            session_id=detail.session.session_id,
            candidate_ids=[approved.candidate_id],
            current_user=user_to_response(admin),
        )

        assert commit.committed_count == 1
        assert commit.partner_summaries == []
        assert commit.topic_summaries[0].topic_label == "Ecosystem Projects"
        assert commit.topic_summaries[0].updates_approved == 1
        assert len(commit.created_topic_update_ids) == 1

        topic_updates = list(
            await session.scalars(
                select(TopicUpdate).where(TopicUpdate.created_by == admin.user_id)
            )
        )
        assert len(topic_updates) == 1
        assert topic_updates[0].status == TopicUpdateStatus.approved.value
        assert topic_updates[0].topic_label == "Ecosystem Projects"
        assert (
            topic_updates[0].source_event_key == f"knowledge-upload-topic:{approved.candidate_id}"
        )
        partner_updates = list(
            await session.scalars(
                select(PartnerUpdate).where(PartnerUpdate.created_by == admin.user_id)
            )
        )
        assert partner_updates == []

        await cleanup_test_records(session, [partner_name], [admin_email])
        await session.commit()


def upload_file(filename: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content))


def docx_bytes(paragraphs: list[str]) -> bytes:
    body = "\n".join(f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>" for text in paragraphs)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w") as package:
        package.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


DocxInlineRuns = list[tuple[str, str | None]]
DocxListItem = (
    tuple[str, int | None, str | None]
    | tuple[str, int | None, str | None, str]
    | tuple[DocxInlineRuns, int | None, str | None]
)


def docx_list_bytes(items: list[DocxListItem]) -> bytes:
    body_parts: list[str] = []
    rel_parts: list[str] = []
    for index, item in enumerate(items, start=1):
        text, level, link = item[:3]
        num_id = item[3] if len(item) > 3 else "10"
        run_xml = f"<w:r><w:t>{escape(text)}</w:t></w:r>"
        if link:
            rel_id = f"rId{index}"
            run_xml = f'<w:hyperlink r:id="{rel_id}">{run_xml}</w:hyperlink>'
            rel_parts.append(
                f'<Relationship Id="{rel_id}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/hyperlink" '
                f'Target="{escape(link)}" TargetMode="External"/>'
            )
        if level is None:
            body_parts.append(f"<w:p>{run_xml}</w:p>")
            continue
        body_parts.append(
            "<w:p>"
            "<w:pPr>"
            '<w:pStyle w:val="ListParagraph"/>'
            "<w:numPr>"
            f'<w:ilvl w:val="{level}"/>'
            f'<w:numId w:val="{num_id}"/>'
            "</w:numPr>"
            "</w:pPr>"
            f"{run_xml}"
            "</w:p>"
        )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body_parts)}</w:body>"
        "</w:document>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(rel_parts)}"
        "</Relationships>"
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w") as package:
        package.writestr("word/document.xml", document_xml)
        package.writestr("word/_rels/document.xml.rels", rels_xml)
    return buffer.getvalue()


def docx_partner_update_table_bytes(
    rows: list[tuple[str, str, list[DocxListItem]]],
) -> bytes:
    body_parts: list[str] = []
    rel_parts: list[str] = []
    rel_counter = 1

    def paragraph_xml(
        text: str | DocxInlineRuns,
        level: int | None = None,
        link: str | None = None,
    ) -> str:
        nonlocal rel_counter
        if isinstance(text, list):
            run_xml_parts = []
            for run_text, run_link in text:
                run_xml = f"<w:r><w:t>{escape(run_text)}</w:t></w:r>"
                if run_link:
                    rel_id = f"rId{rel_counter}"
                    rel_counter += 1
                    run_xml = f'<w:hyperlink r:id="{rel_id}">{run_xml}</w:hyperlink>'
                    rel_parts.append(
                        f'<Relationship Id="{rel_id}" '
                        'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                        'relationships/hyperlink" '
                        f'Target="{escape(run_link)}" TargetMode="External"/>'
                    )
                run_xml_parts.append(run_xml)
            run_xml = "".join(run_xml_parts)
        else:
            run_xml = f"<w:r><w:t>{escape(text)}</w:t></w:r>"
            if link:
                rel_id = f"rId{rel_counter}"
                rel_counter += 1
                run_xml = f'<w:hyperlink r:id="{rel_id}">{run_xml}</w:hyperlink>'
                rel_parts.append(
                    f'<Relationship Id="{rel_id}" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                    'relationships/hyperlink" '
                    f'Target="{escape(link)}" TargetMode="External"/>'
                )
        if level is None:
            return f"<w:p>{run_xml}</w:p>"
        return (
            "<w:p>"
            "<w:pPr>"
            '<w:pStyle w:val="ListParagraph"/>'
            "<w:numPr>"
            f'<w:ilvl w:val="{level}"/>'
            '<w:numId w:val="16"/>'
            "</w:numPr>"
            "</w:pPr>"
            f"{run_xml}"
            "</w:p>"
        )

    def cell_xml(paragraphs: list[DocxListItem] | list[tuple[str, None, None]]) -> str:
        return f"<w:tc>{''.join(paragraph_xml(*item[:3]) for item in paragraphs)}</w:tc>"

    header = (
        "<w:tr>"
        f"{cell_xml([('Partner Category', None, None)])}"
        f"{cell_xml([('Company', None, None)])}"
        f"{cell_xml([('Update', None, None)])}"
        "</w:tr>"
    )
    body_parts.append(header)
    for category, company, updates in rows:
        body_parts.append(
            "<w:tr>"
            f"{cell_xml([(category, None, None)])}"
            f"{cell_xml([(company, None, None)])}"
            f"{cell_xml(updates)}"
            "</w:tr>"
        )

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:tbl>{''.join(body_parts)}</w:tbl></w:body>"
        "</w:document>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(rel_parts)}"
        "</Relationships>"
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w") as package:
        package.writestr("word/document.xml", document_xml)
        package.writestr("word/_rels/document.xml.rels", rels_xml)
    return buffer.getvalue()


PptxParagraphInput = tuple[str, int] | tuple[str, int, str]


def pptx_google_workstream_bytes(
    rows: list[tuple[str, list[PptxParagraphInput], list[PptxParagraphInput]]],
) -> bytes:
    rel_parts: list[str] = []
    rel_counter = 1

    def attr_escape(value: str) -> str:
        return escape(value, {'"': "&quot;"})

    def cell(paragraphs: list[PptxParagraphInput] | list[tuple[str, int]]) -> str:
        nonlocal rel_counter
        paragraph_xml: list[str] = []
        for item in paragraphs:
            text, level = item[:2]
            link = item[2] if len(item) > 2 else None
            rel_xml = ""
            if link:
                rel_id = f"rId{rel_counter}"
                rel_counter += 1
                rel_xml = f'<a:rPr><a:hlinkClick r:id="{rel_id}"/></a:rPr>'
                rel_parts.append(
                    f'<Relationship Id="{rel_id}" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                    'relationships/hyperlink" '
                    f'Target="{attr_escape(link)}" TargetMode="External"/>'
                )
            paragraph_xml.append(
                f'<a:p><a:pPr lvl="{level}"/><a:r>{rel_xml}<a:t>{escape(text)}</a:t></a:r></a:p>'
            )
        return (
            "<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>"
            f"{''.join(paragraph_xml)}"
            "</a:txBody><a:tcPr/></a:tc>"
        )

    header = (
        "<a:tr>"
        f"{cell([('Workstream', 0)])}"
        f"{cell([('CY 2026 Targets', 0)])}"
        f"{cell([('Recent Updates', 0)])}"
        "</a:tr>"
    )
    row_xml = []
    for workstream, targets, updates in rows:
        row_xml.append(f"<a:tr>{cell([(workstream, 0)])}{cell(targets)}{cell(updates)}</a:tr>")
    slide_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<p:cSld><p:spTree><p:graphicFrame><a:graphic><a:graphicData>"
        f"<a:tbl>{header}{''.join(row_xml)}</a:tbl>"
        "</a:graphicData></a:graphic></p:graphicFrame></p:spTree></p:cSld>"
        "</p:sld>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(rel_parts)}"
        "</Relationships>"
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w") as package:
        package.writestr("ppt/slides/slide3.xml", slide_xml)
        package.writestr("ppt/slides/_rels/slide3.xml.rels", rels_xml)
    return buffer.getvalue()


def pptx_microsoft_workstream_bytes(
    rows: list[
        tuple[
            list[PptxParagraphInput],
            list[PptxParagraphInput],
            list[PptxParagraphInput],
            list[PptxParagraphInput],
            list[PptxParagraphInput],
            str,
        ]
    ],
) -> bytes:
    def cell(
        paragraphs: list[PptxParagraphInput] | list[tuple[str, int]], fill: str | None = None
    ) -> str:
        paragraph_xml: list[str] = []
        for item in paragraphs:
            text, level = item[:2]
            paragraph_xml.append(
                f'<a:p><a:pPr lvl="{level}"/><a:r><a:t>{escape(text)}</a:t></a:r></a:p>'
            )
        fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else ""
        return (
            "<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>"
            f"{''.join(paragraph_xml)}"
            f"</a:txBody><a:tcPr>{fill_xml}</a:tcPr></a:tc>"
        )

    header = (
        "<a:tr>"
        f"{cell([('Workstream', 0)])}"
        f"{cell([('Workload', 0)])}"
        f"{cell([('Objective', 0)])}"
        f"{cell([('Updates & Blockers', 0)])}"
        f"{cell([('Go to Green Action', 0)])}"
        f"{cell([('RAG', 0)])}"
        "</a:tr>"
    )
    row_xml = []
    for workstream, workload, objective, updates, go_green, rag_fill in rows:
        row_xml.append(
            "<a:tr>"
            f"{cell(workstream)}"
            f"{cell(workload)}"
            f"{cell(objective)}"
            f"{cell(updates)}"
            f"{cell(go_green)}"
            f"{cell([], rag_fill)}"
            "</a:tr>"
        )
    slide_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<p:cSld><p:spTree><p:graphicFrame><a:graphic><a:graphicData>"
        f"<a:tbl>{header}{''.join(row_xml)}</a:tbl>"
        "</a:graphicData></a:graphic></p:graphicFrame></p:spTree></p:cSld>"
        "</p:sld>"
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w") as package:
        package.writestr("ppt/slides/slide2.xml", slide_xml)
    return buffer.getvalue()


def test_knowledge_upload_analyzer_maps_headings_without_turning_days_into_years(tmp_path) -> None:
    vmware_id = uuid.uuid4()
    suse_id = uuid.uuid4()
    source = tmp_path / "Software EcosystemMonthly Status Report_July 24 2026.txt"
    source.write_text(
        "\n".join(
            [
                "VMware",
                (
                    "VMware developed an Arm Server Qualification Partner Test Suite, with Arm "
                    "planning internal qualification testing the week of August 12, pending CRB "
                    "availability."
                ),
                "",
                "SUSE",
                "SUSE is issuing a blog that highlights Day 0 portfolio readiness for AGI CPU.",
            ]
        ),
        encoding="utf-8",
    )

    candidates = build_knowledge_upload_candidates(
        file_path=source,
        original_filename=source.name,
        upload_id=uuid.uuid4(),
        selected_partner_id=None,
        active_partners=[
            Partner(partner_id=vmware_id, name="VMware", status=PartnerStatus.active.value),
            Partner(partner_id=suse_id, name="SUSE", status=PartnerStatus.active.value),
        ],
        description=None,
    )

    assert infer_cycle_month("week of August 12, pending CRB availability") is None
    assert len(candidates) == 2
    assert {candidate.partner_id for candidate in candidates} == {vmware_id, suse_id}
    assert {candidate.cycle_month for candidate in candidates} == {date(2026, 7, 1)}
    assert {candidate.review_status for candidate in candidates} == {"ready"}


def test_knowledge_upload_analyzer_preserves_docx_nested_partner_context(tmp_path) -> None:
    partner_names = [
        "AWS",
        "Google",
        "Microsoft",
        "Redis",
        "VMware",
        "Elastic",
        "Salesforce",
        "MongoDB",
        "Tinkerblox",
        "Cohere",
        "Uber",
        "Red Hat",
        "SUSE",
        "Canonical",
    ]
    partner_ids = {name: uuid.uuid4() for name in partner_names}
    source = tmp_path / "Software Ecosystem Monthly Status Report_Feb 28 2026.docx"
    source.write_bytes(
        docx_list_bytes(
            [
                ("AWS:", 1, None),
                ("Google:", 1, None),
                ("Weekly GTM calls with Google Cloud PM team", 2, "https://example.com/gtm"),
                ("Tracking Vertex AI service transition to Axion", 3, None),
                ("Announcement is planned at GCN", 4, None),
                ("Updating C4A CLU AI/ML data to support", 4, None),
                ("GTM deliverables tracker", 3, "https://example.com/tracker"),
                ("Google Cloud Next (GCN) 2026 activities", 2, None),
                ("10x10 booth with demos", 3, None),
                ("Arm/Google Day 0 workshop has been approved", 3, None),
                ("Working with organizers on agenda and logistics", 4, None),
                ("Published 4 Learning Paths specific to Google Cloud", 2, None),
                ("CCA workstream", 2, None),
                ("Updates to CCA spec are being discussed by both teams", 3, None),
                ("Google requesting a schedule acceleration", 3, None),
                ("Microsoft:", 1, None),
                ("Customer migrations dashboard updated", 2, None),
                ("Optum POC finished with positive benchmark results", None, None),
                ("Azure Migrate kick off occurred on Feb 24th", 2, None),
                ("Fabric Spark engagement is moving forward", 2, None),
                ("Arm MCP Server internal blog published", 2, None),
                ("MSFT PSA enablement session occurring on Mar 6th", 2, None),
                ("Learning Paths specific to Azure published", 2, None),
                ("Copilot workstream planning started", 2, None),
                ("ISVs (Design Target Deck)", 0, None),
                ("Redis: Arm and Redis teams have aligned on quantization support", 1, None),
                ("VMware: Supported 3-way panel with NVIDIA/VMW", 1, None),
                ("Elastic: Included entire product portfolio on Arm dashboard", 1, None),
                ("Salesforce: Multiple services moved to Graviton", 1, None),
                ("MongoDB: ATP team demoed the latest tool", 1, None),
                (
                    "Tinkerblox: Learning path has been published",
                    1,
                    "https://example.com/tinkerblox",
                ),
                ("Cohere: Intro call occurred to discuss SLM engagement", 1, None),
                ("Uber", 1, None),
                ("Monthly engineering sync up meetings began", 2, None),
                ("Planning Tech Day in May", 2, None),
                ("OSVs (Red Hat, SUSE, Canonical)", 1, None),
                ("Securing executive participation for Arm Everywhere event", 0, None, "18"),
                ("Now targeting A1 silicon for certification across all OSVs", 0, None, "18"),
                ("14 CRB units allocated", 1, None, "18"),
                (
                    "CRB delivery in September increases the risk to get certs by November",
                    1,
                    None,
                    "18",
                ),
                ("Latest details and status in the tracker.", 0, "https://example.com/osv", "18"),
                ("Ecosystem Projects:", 1, None),
                ("Ecosystem Dashboard", 0, None, "16"),
                ("500+ recommended packages", 1, None, "16"),
                ("Marketing:", 1, None),
                (
                    "Cloud Marketing Initiatives Tracked here",
                    0,
                    "https://example.com/marketing",
                    "16",
                ),
                ("Upcoming Conferences and Events", None, None),
                ("Google Cloud next, April 22-24, 2026", 0, None, "16"),
                ("Upcoming PTO", None, None),
                ("Yan: June 1-5", 0, None, "16"),
            ]
        )
    )

    candidates = build_knowledge_upload_candidates(
        file_path=source,
        original_filename=source.name,
        upload_id=uuid.uuid4(),
        selected_partner_id=None,
        active_partners=[
            Partner(
                partner_id=partner_id,
                name=partner_name,
                status=PartnerStatus.active.value,
            )
            for partner_name, partner_id in partner_ids.items()
        ],
        description=None,
    )

    assert not [candidate for candidate in candidates if candidate.partner_id == partner_ids["AWS"]]

    google_candidates = [
        candidate for candidate in candidates if candidate.partner_id == partner_ids["Google"]
    ]
    assert len(google_candidates) == 4
    assert "Weekly GTM calls" in google_candidates[0].summary
    assert "Google Cloud Next" in google_candidates[1].summary
    weekly = next(
        candidate for candidate in google_candidates if "Weekly GTM calls" in candidate.summary
    )
    assert "<ul><li>Tracking Vertex AI service transition to Axion" in weekly.summary
    assert "<li>Announcement is planned at GCN</li>" in weekly.summary
    assert '<a href="https://example.com/tracker"' in weekly.summary
    gcn = next(
        candidate for candidate in google_candidates if "Google Cloud Next" in candidate.summary
    )
    assert "10x10 booth with demos" in gcn.summary
    assert "Working with organizers on agenda and logistics" in gcn.summary
    linked_candidate = next(
        candidate for candidate in google_candidates if "tracker" in candidate.summary
    )
    assert linked_candidate.source_url == "https://example.com/gtm"
    assert "https://example.com/gtm" in linked_candidate.evidence_snippet
    assert "https://example.com/tracker" in linked_candidate.evidence_snippet

    microsoft_candidates = [
        candidate for candidate in candidates if candidate.partner_id == partner_ids["Microsoft"]
    ]
    assert len(microsoft_candidates) == 7
    assert any(
        "Optum POC finished with positive benchmark results" in candidate.summary
        for candidate in microsoft_candidates
    )

    for partner_name in [
        "Redis",
        "VMware",
        "Elastic",
        "Salesforce",
        "MongoDB",
        "Tinkerblox",
        "Cohere",
    ]:
        partner_candidates = [
            candidate
            for candidate in candidates
            if candidate.partner_id == partner_ids[partner_name]
        ]
        assert len(partner_candidates) == 1
    assert (
        "Redis:"
        not in next(
            candidate for candidate in candidates if candidate.partner_id == partner_ids["Redis"]
        ).summary
    )

    uber_candidates = [
        candidate for candidate in candidates if candidate.partner_id == partner_ids["Uber"]
    ]
    assert len(uber_candidates) == 2

    crb_candidates = [
        candidate for candidate in candidates if "14 CRB units allocated" in candidate.summary
    ]
    assert {candidate.partner_id for candidate in crb_candidates} == {
        partner_ids["Red Hat"],
        partner_ids["SUSE"],
        partner_ids["Canonical"],
    }
    assert all(
        "CRB delivery in September increases the risk" in candidate.summary
        for candidate in crb_candidates
    )
    assert {candidate.review_status for candidate in crb_candidates} == {"ready"}

    topic_labels = {candidate.raw_label for candidate in candidates if candidate.partner_id is None}
    assert topic_labels == {
        "Ecosystem Projects",
        "Marketing",
        "Upcoming Conferences and Events",
        "Upcoming PTO",
    }
    marketing = next(candidate for candidate in candidates if candidate.raw_label == "Marketing")
    assert marketing.review_status == "needs_mapping"
    assert '<a href="https://example.com/marketing"' in marketing.summary


def test_knowledge_upload_analyzer_fans_out_bare_partner_groups(tmp_path) -> None:
    partner_names = ["Red Hat", "SUSE", "Canonical"]
    partner_ids = {name: uuid.uuid4() for name in partner_names}
    source = tmp_path / "Software Ecosystem Monthly Status Report_Jan 30 2026.docx"
    source.write_bytes(
        docx_list_bytes(
            [
                ("Red Hat, SUSE, Canonical", 1, None),
                (
                    "Requested A1 silicon for certification pushing the CRB deliveries into "
                    "September.",
                    2,
                    None,
                ),
                (
                    "New timelines will be tight with a heightened risk to Red Hat and SUSE certs",
                    2,
                    None,
                ),
                ("Latest details and status in the tracker.", 2, "https://example.com/osv"),
            ]
        )
    )

    candidates = build_knowledge_upload_candidates(
        file_path=source,
        original_filename=source.name,
        upload_id=uuid.uuid4(),
        selected_partner_id=None,
        active_partners=[
            Partner(
                partner_id=partner_id,
                name=partner_name,
                status=PartnerStatus.active.value,
            )
            for partner_name, partner_id in partner_ids.items()
        ],
        description=None,
    )

    assert len(candidates) == 9
    assert {candidate.partner_id for candidate in candidates} == set(partner_ids.values())
    assert {candidate.raw_label for candidate in candidates} == set(partner_names)
    assert {candidate.review_status for candidate in candidates} == {"ready"}
    linked_candidates = [
        candidate for candidate in candidates if "Latest details and status" in candidate.summary
    ]
    assert len(linked_candidates) == 3
    assert all(
        '<a href="https://example.com/osv"' in candidate.summary for candidate in linked_candidates
    )


def test_knowledge_upload_analyzer_strips_inline_partner_prefix_from_update(tmp_path) -> None:
    partner_id = uuid.uuid4()
    source = tmp_path / "Software Ecosystem Monthly Status Report_Jan 30 2026.txt"
    source.write_text(
        (
            "Salesforce: Multiple services moved to Graviton; migrations for CRM "
            "application blocked due to Java performance bottlenecks."
        ),
        encoding="utf-8",
    )

    candidates = build_knowledge_upload_candidates(
        file_path=source,
        original_filename=source.name,
        upload_id=uuid.uuid4(),
        selected_partner_id=None,
        active_partners=[
            Partner(
                partner_id=partner_id,
                name="Salesforce",
                status=PartnerStatus.active.value,
            )
        ],
        description=None,
    )

    assert len(candidates) == 1
    assert candidates[0].partner_id == partner_id
    assert candidates[0].raw_label == "Salesforce"
    assert candidates[0].summary.startswith("Multiple services moved to Graviton")
    assert not candidates[0].summary.startswith("Salesforce:")


def test_knowledge_upload_analyzer_preserves_docx_table_cell_bullet_structure(
    tmp_path,
) -> None:
    google_id = uuid.uuid4()
    source = tmp_path / "Software EcosystemMonthly Status Report_July 24 2026.docx"
    source.write_bytes(
        docx_partner_update_table_bytes(
            [
                (
                    "CSP",
                    "Google Cloud",
                    [
                        ("Last Quarterly Technical Review (QTR) readout and ARs", 0, None),
                        (
                            "Prepared communication about personnel changes in Arm team "
                            "covering Google",
                            1,
                            None,
                        ),
                        ("Next QTR is tentatively scheduled for Sept. 2026", 1, None),
                        (
                            "We will be discussing QTR cadence and other technical workstreams "
                            "at APM",
                            2,
                            None,
                        ),
                        ("Held SW interlock call to cover ARs from last QTR", 0, None),
                        (
                            "Started bi-weekly calls with Google Cloud product marketing team",
                            0,
                            None,
                        ),
                        (
                            "Axion family GTM deliverables tracker",
                            1,
                            "https://example.com/google-gtm",
                        ),
                        (
                            "Vertex AI is now a part of Gemini Enterprise Agent Platform "
                            "and generally available on Axion is GA",
                            0,
                            None,
                        ),
                        (
                            [
                                (
                                    "There was no public announcement that we can support with ",
                                    None,
                                ),
                                ("updated LLM benchmarks", "https://example.com/llm"),
                            ],
                            1,
                            None,
                        ),
                    ],
                )
            ]
        )
    )

    candidates = build_knowledge_upload_candidates(
        file_path=source,
        original_filename=source.name,
        upload_id=uuid.uuid4(),
        selected_partner_id=None,
        active_partners=[
            Partner(partner_id=google_id, name="Google", status=PartnerStatus.active.value)
        ],
        description=None,
    )

    assert len(candidates) == 4
    assert all(candidate.partner_id == google_id for candidate in candidates)
    assert all(candidate.review_status == "ready" for candidate in candidates)
    assert "Last Quarterly Technical Review" in candidates[0].summary
    assert "<ul><li>Prepared communication" in candidates[0].summary
    assert "<li>We will be discussing QTR cadence" in candidates[0].summary
    assert "<p>Held SW interlock call to cover ARs from last QTR</p>" == candidates[1].summary
    assert "Started bi-weekly calls" in candidates[2].summary
    assert '<a href="https://example.com/google-gtm"' in candidates[2].summary
    assert "Vertex AI is now a part" in candidates[3].summary
    assert (
        'There was no public announcement that we can support with <a href="https://example.com/llm"'
        in candidates[3].summary
    )
    assert (
        '<a href="https://example.com/llm" target="_blank" rel="noopener noreferrer">'
        "There was no public announcement"
        not in candidates[3].summary
    )
    assert "Held SW interlock call" not in candidates[0].summary
    assert "Parsed from partner update table." in (candidates[0].parser_notes or "")


def test_knowledge_upload_analyzer_extracts_google_workstream_pptx_rows(tmp_path) -> None:
    google_id = uuid.uuid4()
    source = tmp_path / "Arm-Google Workstreams - June 2026.pptx"
    source.write_bytes(
        pptx_google_workstream_bytes(
            [
                (
                    "Software Ecosystem",
                    [
                        ("MPAM: Complete upstreaming of MPAM (resctrl)", 0),
                        (
                            "RME/CCA: Upstream status, Linaro joint DA work "
                            "(tracked in the CCA workstream)",
                            0,
                        ),
                        ("RAS: Improve quality of firmware first error flows", 0),
                    ],
                    [
                        ("Most recent discussion: Mar 17, 2026", 0),
                        (
                            "Update on latest MPAM upstreaming (resctrl). Kernel patches "
                            "for Arm have been merged!",
                            0,
                        ),
                        ("ARs:", 0),
                        ("Replacement for Eric Christopher (toolchain)", 1),
                        ("GTM deliverables tracker", 0, "https://example.com/google-gtm"),
                    ],
                ),
                (
                    "AI/ML",
                    [
                        ("GCP C4A: Launch, positioning and ramp for ML inference", 0),
                    ],
                    [
                        ("Most recent meetings - June 18", 0),
                        ("Google will run SC26 BoF on JAX and XLA", 0),
                    ],
                ),
            ]
        )
    )

    candidates = build_knowledge_upload_candidates(
        file_path=source,
        original_filename=source.name,
        upload_id=uuid.uuid4(),
        selected_partner_id=None,
        active_partners=[
            Partner(partner_id=google_id, name="Google", status=PartnerStatus.active.value)
        ],
        description=None,
    )

    assert len(candidates) == 2
    assert {candidate.partner_id for candidate in candidates} == {google_id}
    assert {candidate.cycle_month for candidate in candidates} == {date(2026, 6, 1)}
    assert {candidate.review_status for candidate in candidates} == {"ready"}

    software = candidates[0]
    assert "<strong>Software Ecosystem work stream</strong>" in software.summary
    assert "<strong>CY2026 Targets:</strong>" in software.summary
    assert "MPAM: Complete upstreaming of MPAM" in software.summary
    assert "<strong>Recent Updates:</strong>" in software.summary
    assert "Kernel patches for Arm have been merged!" in software.summary
    assert "<li>ARs:<ul><li>Replacement for Eric Christopher" in software.summary
    assert '<a href="https://example.com/google-gtm"' in software.summary
    assert software.source_url == "https://example.com/google-gtm"
    assert "https://example.com/google-gtm" in software.evidence_snippet

    ai_ml = candidates[1]
    assert "<strong>AI/ML work stream</strong>" in ai_ml.summary
    assert "Google will run SC26 BoF on JAX and XLA" in ai_ml.summary


def test_knowledge_upload_analyzer_extracts_microsoft_workstream_pptx_rows(tmp_path) -> None:
    microsoft_id = uuid.uuid4()
    source = tmp_path / "Internal Arm Microsoft Workstream Update-June'26.pptx"
    source.write_bytes(
        pptx_microsoft_workstream_bytes(
            [
                (
                    [("1P", 0)],
                    [("MDE, M365, Teams, SQL, .NET", 0)],
                    [("Test and compare 1P workloads on C200 v/s C100", 0)],
                    [
                        (
                            "Cobalt-200 validation produced actionable signals across "
                            "M365 and Windows workloads.",
                            0,
                        )
                    ],
                    [("Consistent VM access expected by mid-May", 0)],
                    "FFC000",
                ),
                (
                    [],
                    [("MDE", 0)],
                    [("Benchmarking of MDE & MTP services to Cobalt", 0)],
                    [("Migration and C200 v/s C100 benchmarking is currently on hold.", 0)],
                    [("New Israel engineering lead to circle back", 0)],
                    "FF0000",
                ),
                (
                    [("Core OS", 0)],
                    [("Hyper-V", 0), ("OpenHCL", 0), ("HAL", 0)],
                    [
                        ("Close gap in Hyper-V performance", 0),
                        ("Hyper-V/CVM Cobalt strategy", 0),
                        ("Build unified HAL framework", 0),
                    ],
                    [
                        ("CCA Plane Enablement:", 0),
                        ("Began prototyping native CCA Plane enablement on Hyper-V", 1),
                    ],
                    [],
                    "92D050",
                ),
            ]
        )
    )

    candidates = build_knowledge_upload_candidates(
        file_path=source,
        original_filename=source.name,
        upload_id=uuid.uuid4(),
        selected_partner_id=None,
        active_partners=[
            Partner(
                partner_id=microsoft_id,
                name="Microsoft",
                status=PartnerStatus.active.value,
            )
        ],
        description=None,
    )

    assert len(candidates) == 5
    assert {candidate.partner_id for candidate in candidates} == {microsoft_id}
    assert {candidate.cycle_month for candidate in candidates} == {date(2026, 6, 1)}
    assert {candidate.review_status for candidate in candidates} == {"ready"}

    first = candidates[0]
    assert "<strong>1P Work Stream</strong>" in first.summary
    assert "<strong>Workload:</strong> MDE, M365, Teams, SQL, .NET" in first.summary
    assert "<strong>Objective:</strong> Test and compare 1P workloads" in first.summary
    assert "<strong>Updates &amp; Blockers:</strong>" in first.summary
    assert "Cobalt-200 validation produced actionable signals" in first.summary
    assert "<strong>Go to Green Action:</strong> Consistent VM access" in first.summary
    assert "<strong>Current Status:</strong> Amber" in first.summary

    inherited = candidates[1]
    assert inherited.section_label == "Slide 1 > 1P > MDE"
    assert "<strong>Current Status:</strong> Red" in inherited.summary

    core_os = candidates[2:]
    assert [candidate.section_label for candidate in core_os] == [
        "Slide 1 > Core OS > Hyper-V",
        "Slide 1 > Core OS > OpenHCL",
        "Slide 1 > Core OS > HAL",
    ]
    assert all("<strong>Core OS Work Stream</strong>" in candidate.summary for candidate in core_os)
    assert all("CCA Plane Enablement" in candidate.summary for candidate in core_os)
    assert all(
        "<strong>Current Status:</strong> Green" in candidate.summary for candidate in core_os
    )


async def cleanup_test_records(
    session: AsyncSession,
    partner_names: list[str],
    emails: list[str],
) -> None:
    partner_ids = select_partner_ids(partner_names)
    user_ids = select_user_ids(emails)
    await session.execute(delete(MemoryChunk).where(MemoryChunk.partner_id.in_(partner_ids)))
    await session.execute(delete(TopicUpdate).where(TopicUpdate.created_by.in_(user_ids)))
    await session.execute(
        delete(KnowledgeUploadCandidate).where(
            KnowledgeUploadCandidate.upload_id.in_(
                select(KnowledgeUpload.upload_id).where(KnowledgeUpload.partner_id.in_(partner_ids))
            )
        )
    )
    await session.execute(delete(PartnerUpdate).where(PartnerUpdate.partner_id.in_(partner_ids)))
    await session.execute(
        delete(KnowledgeUpload).where(KnowledgeUpload.partner_id.in_(partner_ids))
    )
    await session.execute(delete(KnowledgeUpload).where(KnowledgeUpload.uploaded_by.in_(user_ids)))
    await session.execute(
        delete(KnowledgeUploadSession).where(KnowledgeUploadSession.uploaded_by.in_(user_ids))
    )
    await session.execute(delete(AgentRun).where(AgentRun.triggered_by.in_(user_ids)))
    await session.execute(
        delete(PartnerContributorAssignment).where(
            PartnerContributorAssignment.partner_id.in_(partner_ids)
        )
    )
    await session.execute(delete(Partner).where(Partner.name.in_(partner_names)))
    await session.execute(delete(UserSession).where(UserSession.user_id.in_(user_ids)))
    await session.execute(
        delete(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(user_ids))
    )
    await session.execute(delete(User).where(User.email.in_(emails)))


def select_partner_ids(partner_names: list[str]):
    return select(Partner.partner_id).where(Partner.name.in_(partner_names))


def select_user_ids(emails: list[str]):
    return select(User.user_id).where(User.email.in_(emails))
