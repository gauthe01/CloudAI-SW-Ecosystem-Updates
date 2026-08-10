import uuid
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.identity import RoleType, User, UserRoleAssignment, UserSession
from app.db.models.knowledge_upload import KnowledgeUpload
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.session import get_session_factory
from app.domains.identity.service import user_to_response
from app.domains.uploads.service import KnowledgeUploadService


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


def upload_file(filename: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content))


async def cleanup_test_records(
    session: AsyncSession,
    partner_names: list[str],
    emails: list[str],
) -> None:
    partner_ids = select_partner_ids(partner_names)
    user_ids = select_user_ids(emails)
    await session.execute(
        delete(KnowledgeUpload).where(KnowledgeUpload.partner_id.in_(partner_ids))
    )
    await session.execute(delete(KnowledgeUpload).where(KnowledgeUpload.uploaded_by.in_(user_ids)))
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
