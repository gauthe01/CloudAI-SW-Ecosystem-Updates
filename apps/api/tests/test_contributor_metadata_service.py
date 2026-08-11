import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType, User, UserRoleAssignment, UserSession
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_metadata import (
    PartnerMetadataRisk,
    PartnerMetadataSnapshot,
    PartnerResourceLink,
)
from app.db.session import get_session_factory
from app.domains.contributor.metadata.schemas import (
    PartnerMetadataRiskPayload,
    PartnerMetadataSaveRequest,
    PartnerResourceLinkPayload,
)
from app.domains.contributor.metadata.service import ContributorMetadataService
from app.domains.identity.service import user_to_response


@pytest.mark.asyncio
async def test_contributor_metadata_save_load_and_overwrite_latest_snapshot() -> None:
    contributor_email = f"metadata-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Metadata Partner {uuid.uuid4()}"
    unassigned_partner_name = f"Metadata Unassigned Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(
            session,
            [partner_name, unassigned_partner_name],
            [contributor_email],
        )
        contributor = User(email=contributor_email, display_name="Metadata Contributor")
        contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
        partner = Partner(
            name=partner_name,
            description="Metadata partner",
            status=PartnerStatus.active.value,
        )
        unassigned_partner = Partner(
            name=unassigned_partner_name,
            description="Unassigned metadata partner",
            status=PartnerStatus.active.value,
        )
        session.add_all([contributor, partner, unassigned_partner])
        await session.flush()
        session.add(
            PartnerContributorAssignment(
                partner_id=partner.partner_id,
                user_id=contributor.user_id,
            )
        )
        await session.commit()

        service = ContributorMetadataService(session)
        current_user = user_to_response(contributor)
        empty_metadata = await service.get_metadata(
            partner_id=partner.partner_id,
            cycle="2026-08",
            current_user=current_user,
        )
        assert empty_metadata.metadata_id is None
        assert empty_metadata.resources == []

        saved_metadata = await service.save_metadata(
            partner_id=partner.partner_id,
            cycle="2026-08",
            payload=PartnerMetadataSaveRequest(
                status="green",
                why_this_partner="Strategic cloud ecosystem priority.",
                business_priority="High",
                highlights_status="Healthy engagement.",
                goals="Land monthly partner updates.",
                execution_timeline="August checkpoint.",
                risks=[
                    PartnerMetadataRiskPayload(
                        description="Delayed integration access",
                        green_action="Confirm owner",
                        severity="amber",
                        assigned_to="Bhumik",
                        ramification="Could delay update automation",
                    )
                ],
                resources=[
                    PartnerResourceLinkPayload(
                        title="AWS Jira",
                        url="https://example.com/jira/AWS-1",
                        description="Primary ticket",
                    )
                ],
            ),
            current_user=current_user,
        )
        assert saved_metadata.metadata_id is not None
        assert saved_metadata.status == "green"
        assert [risk.description for risk in saved_metadata.risks] == [
            "Delayed integration access"
        ]
        assert [resource.title for resource in saved_metadata.resources] == ["AWS Jira"]

        overwritten_metadata = await service.save_metadata(
            partner_id=partner.partner_id,
            cycle="2026-08",
            payload=PartnerMetadataSaveRequest(
                status="amber",
                why_this_partner="Strategic cloud ecosystem priority remains valid.",
                business_priority="Medium",
                highlights_status="Needs attention.",
                goals="Close monthly partner risks.",
                risks=[
                    PartnerMetadataRiskPayload(
                        description="New monthly risk",
                        severity="red",
                    )
                ],
                resources=[
                    PartnerResourceLinkPayload(
                        title="AWS SharePoint",
                        url="https://example.com/sharepoint/aws",
                    )
                ],
            ),
            current_user=current_user,
        )

        assert overwritten_metadata.metadata_id == saved_metadata.metadata_id
        assert overwritten_metadata.status == "amber"
        assert overwritten_metadata.why_this_partner == "Strategic cloud ecosystem priority remains valid."
        assert [risk.description for risk in overwritten_metadata.risks] == ["New monthly risk"]
        assert [resource.title for resource in overwritten_metadata.resources] == [
            "AWS SharePoint"
        ]

        with pytest.raises(ValidationError):
            PartnerMetadataSaveRequest(
                status="green",
                why_this_partner=" ",
                business_priority="High",
                highlights_status="Healthy engagement.",
                goals="Land monthly partner updates.",
            )

        snapshot_count = await count_rows(
            session,
            select(func.count())
            .select_from(PartnerMetadataSnapshot)
            .where(PartnerMetadataSnapshot.partner_id == partner.partner_id),
        )
        assert snapshot_count == 1

        with pytest.raises(HTTPException) as exc_info:
            await service.get_metadata(
                partner_id=unassigned_partner.partner_id,
                cycle="2026-08",
                current_user=current_user,
            )
        assert exc_info.value.status_code == 403

        await cleanup_test_records(
            session,
            [partner_name, unassigned_partner_name],
            [contributor_email],
        )
        await session.commit()


async def cleanup_test_records(
    session: AsyncSession,
    partner_names: list[str],
    emails: list[str],
) -> None:
    partner_ids = select_partner_ids(partner_names)
    metadata_ids = select(PartnerMetadataSnapshot.metadata_id).where(
        PartnerMetadataSnapshot.partner_id.in_(partner_ids)
    )
    await session.execute(
        delete(PartnerMetadataRisk).where(PartnerMetadataRisk.metadata_id.in_(metadata_ids))
    )
    await session.execute(
        delete(PartnerResourceLink).where(PartnerResourceLink.partner_id.in_(partner_ids))
    )
    await session.execute(
        delete(PartnerMetadataSnapshot).where(PartnerMetadataSnapshot.partner_id.in_(partner_ids))
    )
    await session.execute(
        delete(PartnerContributorAssignment).where(
            PartnerContributorAssignment.partner_id.in_(partner_ids)
        )
    )
    await session.execute(delete(Partner).where(Partner.name.in_(partner_names)))
    await session.execute(
        delete(UserSession).where(UserSession.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(delete(User).where(User.email.in_(emails)))


def select_partner_ids(partner_names: list[str]):
    return select(Partner.partner_id).where(Partner.name.in_(partner_names))


def select_user_ids(emails: list[str]):
    return select(User.user_id).where(User.email.in_(emails))


async def count_rows(session: AsyncSession, statement) -> int:
    result = await session.execute(statement)
    return int(result.scalar_one())
