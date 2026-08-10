import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType, User, UserRoleAssignment, UserSession
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.db.session import get_session_factory
from app.domains.contributor.partners.service import ContributorPartnerService
from app.domains.contributor.updates.schemas import (
    ManualUpdateCreateRequest,
    PartnerUpdateCreatePayload,
    PartnerUpdateEditRequest,
)
from app.domains.contributor.updates.service import ContributorUpdateService
from app.domains.identity.service import user_to_response


@pytest.mark.asyncio
async def test_contributor_update_lifecycle_and_dashboard_counts() -> None:
    contributor_email = f"updates-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"Updates Partner {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [contributor_email])
        contributor = User(email=contributor_email, display_name="Updates Contributor")
        contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
        partner = Partner(
            name=partner_name,
            description="Updates partner",
            status=PartnerStatus.active.value,
        )
        session.add_all([contributor, partner])
        await session.flush()
        session.add(
            PartnerContributorAssignment(
                partner_id=partner.partner_id,
                user_id=contributor.user_id,
            )
        )
        await session.commit()

        current_user = user_to_response(contributor)
        update_service = ContributorUpdateService(session)
        manual_update = await update_service.create_manual_update(
            partner_id=partner.partner_id,
            cycle="2026-08",
            payload=ManualUpdateCreateRequest(
                title="Manual partner checkpoint",
                summary="Contributor manually captured this update.",
            ),
            current_user=current_user,
        )
        assert manual_update.status == PartnerUpdateStatus.pending
        assert manual_update.source_type == "manual"
        assert manual_update.source_label is None
        assert manual_update.source_url is None

        first_update = await update_service.create_pending_update(
            partner_id=partner.partner_id,
            cycle="2026-08",
            payload=PartnerUpdateCreatePayload(
                title="Jira blocker resolved",
                summary="The partner resolved the integration blocker.",
                source_type="jira",
                source_label="AWS-123",
                source_url="https://example.com/jira/AWS-123",
            ),
            current_user=current_user,
        )
        second_update = await update_service.create_pending_update(
            partner_id=partner.partner_id,
            cycle="2026-08",
            payload=PartnerUpdateCreatePayload(
                title="Slack thread needs review",
                summary="A Slack thread produced a draft update.",
                source_type="slack",
                source_label="#aws-partner",
            ),
            current_user=current_user,
        )

        pending_updates = await update_service.list_updates(
            partner_id=partner.partner_id,
            cycle="2026-08",
            update_status=PartnerUpdateStatus.pending,
            current_user=current_user,
        )
        assert {update.update_id for update in pending_updates} == {
            manual_update.update_id,
            first_update.update_id,
            second_update.update_id,
        }

        edited_update = await update_service.edit_pending_update(
            partner_id=partner.partner_id,
            update_id=first_update.update_id,
            payload=PartnerUpdateEditRequest(
                title="Jira blocker resolved for August",
                summary="Contributor edited this update before approval.",
            ),
            current_user=current_user,
        )
        assert edited_update.title == "Jira blocker resolved for August"

        approved_update = await update_service.approve_update(
            partner_id=partner.partner_id,
            update_id=first_update.update_id,
            current_user=current_user,
        )
        assert approved_update.status == PartnerUpdateStatus.approved
        assert approved_update.approved_by == contributor.user_id
        assert approved_update.approved_at is not None

        dismissed_update = await update_service.dismiss_update(
            partner_id=partner.partner_id,
            update_id=second_update.update_id,
            current_user=current_user,
        )
        assert dismissed_update.status == PartnerUpdateStatus.rejected
        assert dismissed_update.rejected_by == contributor.user_id

        manual_approved_update = await update_service.approve_update(
            partner_id=partner.partner_id,
            update_id=manual_update.update_id,
            current_user=current_user,
        )
        assert manual_approved_update.status == PartnerUpdateStatus.approved

        with pytest.raises(HTTPException) as exc_info:
            await update_service.edit_pending_update(
                partner_id=partner.partner_id,
                update_id=first_update.update_id,
                payload=PartnerUpdateEditRequest(
                    title="Cannot edit approved",
                    summary="Approved updates are read-only.",
                ),
                current_user=current_user,
            )
        assert exc_info.value.status_code == 409

        approved_updates = await update_service.list_updates(
            partner_id=partner.partner_id,
            cycle="2026-08",
            update_status=PartnerUpdateStatus.approved,
            current_user=current_user,
        )
        assert {update.update_id for update in approved_updates} == {
            manual_update.update_id,
            first_update.update_id,
        }

        pending_after_actions = await update_service.list_updates(
            partner_id=partner.partner_id,
            cycle="2026-08",
            update_status=PartnerUpdateStatus.pending,
            current_user=current_user,
        )
        assert pending_after_actions == []

        partner_service = ContributorPartnerService(session)
        dashboard_context = await partner_service.get_dashboard_context(
            partner_id=partner.partner_id,
            current_user=current_user,
        )
        assert dashboard_context.tab_counts.pending_updates == 0
        assert dashboard_context.tab_counts.approved_updates == 2
        assert dashboard_context.partner.updates_count == 2
        assert dashboard_context.partner.last_activity_at is not None

        await cleanup_test_records(session, [partner_name], [contributor_email])
        await session.commit()


def test_manual_update_requires_non_blank_text() -> None:
    with pytest.raises(ValidationError):
        ManualUpdateCreateRequest(title="   ", summary="Valid summary")

    with pytest.raises(ValidationError):
        ManualUpdateCreateRequest(title="Valid title", summary="   ")


def test_update_summary_allows_only_supported_rich_text() -> None:
    payload = PartnerUpdateEditRequest(
        title="Formatted update",
        summary=(
            '<b>Bold</b><i>Italic</i><u>Underline</u>'
            '<ol><li>One</li></ol><ul><li>Two</li></ul>'
            '<a href="https://example.com/path" onclick="alert(1)">Link</a>'
            '<a href="javascript:alert(1)">Unsafe</a>'
            '<script>alert(1)</script>'
            '<span style="font-size: 72px">Plain</span>'
        ),
    )

    assert "<b>Bold</b>" in payload.summary
    assert "<i>Italic</i>" in payload.summary
    assert "<u>Underline</u>" in payload.summary
    assert "<ol><li>One</li></ol>" in payload.summary
    assert "<ul><li>Two</li></ul>" in payload.summary
    assert 'href="https://example.com/path"' in payload.summary
    assert "onclick" not in payload.summary
    assert "javascript:" not in payload.summary
    assert "script" not in payload.summary
    assert "font-size" not in payload.summary
    assert "Plain" in payload.summary


async def cleanup_test_records(
    session: AsyncSession,
    partner_names: list[str],
    emails: list[str],
) -> None:
    partner_ids = select_partner_ids(partner_names)
    await session.execute(delete(PartnerUpdate).where(PartnerUpdate.partner_id.in_(partner_ids)))
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
