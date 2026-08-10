import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.identity import (
    RoleType,
    User,
    UserLocalCredential,
    UserRoleAssignment,
    UserSession,
)
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.session import get_session_factory
from app.domains.admin.partners.schemas import (
    AdminPartnerCreateRequest,
    AdminPartnerUpdateRequest,
)
from app.domains.admin.partners.service import AdminPartnerService
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.service import user_to_response


@pytest.mark.asyncio
async def test_admin_can_create_update_archive_and_restore_partner_assignment() -> None:
    admin_email = f"partner-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"partner-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        repository = IdentityRepository(session)
        admin = repository.add_user_with_local_password(
            email=admin_email,
            display_name="Partner Admin",
            password_hash=hash_password("test-password"),
            roles=[RoleType.admin],
        )
        contributor = repository.add_user(
            email=contributor_email,
            display_name="Partner Contributor",
            roles=[RoleType.contributor],
        )
        await session.commit()

        service = AdminPartnerService(session)
        created_partner = await service.create_partner(
            payload=AdminPartnerCreateRequest(
                name=partner_name,
                description="Important partner",
                assigned_contributor_user_ids=[contributor.user_id],
            ),
            current_admin=user_to_response(admin),
        )

        assert created_partner.name == partner_name
        assert created_partner.status == PartnerStatus.active
        assert [user.email for user in created_partner.assigned_contributors] == [
            contributor_email
        ]

        renamed_partner = await service.update_partner(
            partner_id=created_partner.partner_id,
            payload=AdminPartnerUpdateRequest(
                name=f"{partner_name} Updated",
                assigned_contributor_user_ids=[],
            ),
            current_admin=user_to_response(admin),
        )

        assert renamed_partner.name == f"{partner_name} Updated"
        assert renamed_partner.assigned_contributors == []

        archived_partner = await service.archive_partner(created_partner.partner_id)
        assert archived_partner.status == PartnerStatus.archived
        assert archived_partner.archived_at is not None

        restored_partner = await service.restore_partner(created_partner.partner_id)
        assert restored_partner.status == PartnerStatus.active
        assert restored_partner.archived_at is None

        await cleanup_test_records(
            session,
            [partner_name, f"{partner_name} Updated"],
            [admin_email, contributor_email],
        )
        await session.commit()


async def cleanup_test_records(
    session: AsyncSession,
    partner_names: list[str],
    emails: list[str],
) -> None:
    await session.execute(
        delete(PartnerContributorAssignment).where(
            PartnerContributorAssignment.partner_id.in_(select_partner_ids(partner_names))
        )
    )
    await session.execute(delete(Partner).where(Partner.name.in_(partner_names)))
    await session.execute(
        delete(UserSession).where(UserSession.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserLocalCredential).where(UserLocalCredential.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(delete(User).where(User.email.in_(emails)))


def select_partner_ids(partner_names: list[str]):
    return select(Partner.partner_id).where(Partner.name.in_(partner_names))


def select_user_ids(emails: list[str]):
    return select(User.user_id).where(User.email.in_(emails))
