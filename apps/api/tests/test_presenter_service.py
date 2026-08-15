import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType, User, UserRoleAssignment, UserSession
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_metadata import (
    PartnerMetadataRisk,
    PartnerMetadataSnapshot,
    PartnerResourceLink,
    ResourceLinkSourceKind,
)
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.db.models.topic_update import TopicUpdate, TopicUpdateStatus
from app.db.session import get_session_factory
from app.domains.presenter.service import PresenterService


@pytest.mark.asyncio
async def test_presenter_reads_approved_updates_across_unassigned_partners() -> None:
    presenter_email = f"presenter-{uuid.uuid4()}@example.com"
    partner_a_name = f"Presenter AWS {uuid.uuid4()}"
    partner_b_name = f"Presenter Uber {uuid.uuid4()}"
    topic_label = f"Presenter Marketing {uuid.uuid4()}"
    cycle = "2031-08"
    cycle_month = date(2031, 8, 1)

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_a_name, partner_b_name], [presenter_email])
        _, partner_a, partner_b = await create_presenter_fixture(
            session,
            presenter_email=presenter_email,
            partner_a_name=partner_a_name,
            partner_b_name=partner_b_name,
            topic_label=topic_label,
            cycle_month=cycle_month,
        )

        service = PresenterService(session)
        partners = await service.list_partners(cycle=cycle)
        partner_names = {partner.name for partner in partners}
        assert {partner_a_name, partner_b_name}.issubset(partner_names)

        all_updates = await service.list_approved_updates(cycle=cycle)
        assert {
            partner_a_name,
            partner_b_name,
            topic_label,
        }.issubset({update.partner_name for update in all_updates})
        assert topic_label in [
            update.partner_name for update in all_updates if update.scope == "topic"
        ]
        assert all(update.source_url for update in all_updates)

        filtered_updates = await service.list_approved_updates(
            cycle=cycle,
            partner_id=partner_a.partner_id,
        )
        assert [update.partner_name for update in filtered_updates] == [partner_a_name]

        searched_updates = await service.list_approved_updates(cycle=cycle, search="decision")
        assert partner_a_name in [update.partner_name for update in searched_updates]

        analysis = await service.get_analysis(cycle=cycle)
        assert analysis.update_count == 3
        assert analysis.partner_count >= 2
        assert analysis.source_mix["jira"] == 1
        assert analysis.source_mix["file"] == 1
        assert analysis.decision_board
        assert any(item.partner_name == partner_a_name for item in analysis.decision_board)

        email = await service.draft_email(cycle=cycle, partner_id=partner_a.partner_id)
        assert email.subject == f"{partner_a_name} Monthly Update - {cycle}"
        assert "Release decision needed" in email.body
        assert partner_b_name not in email.body
        assert topic_label not in email.body

        all_partner_email = await service.draft_email(cycle=cycle)
        assert f"{topic_label} - Cloud Marketing Initiatives Tracked here" in all_partner_email.body
        assert "<p>" not in all_partner_email.body
        assert "<a href=" not in all_partner_email.body
        assert (
            "Cloud Marketing Initiatives Tracked here (https://example.com/marketing)"
            in all_partner_email.body
        )

        await cleanup_test_records(session, [partner_a_name, partner_b_name], [presenter_email])
        await session.commit()


@pytest.mark.asyncio
async def test_presenter_metadata_is_read_only_for_single_partner() -> None:
    presenter_email = f"presenter-metadata-{uuid.uuid4()}@example.com"
    partner_a_name = f"Presenter Metadata AWS {uuid.uuid4()}"
    partner_b_name = f"Presenter Metadata Uber {uuid.uuid4()}"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_a_name, partner_b_name], [presenter_email])
        _, partner_a, _ = await create_presenter_fixture(
            session,
            presenter_email=presenter_email,
            partner_a_name=partner_a_name,
            partner_b_name=partner_b_name,
            topic_label=f"Presenter Metadata Topic {uuid.uuid4()}",
        )

        service = PresenterService(session)
        metadata = await service.get_partner_metadata(
            cycle="2026-08",
            partner_id=partner_a.partner_id,
        )

        assert metadata.partner_name == partner_a_name
        assert metadata.status == "amber"
        assert metadata.highlights_status == "Release validation needs attention."
        assert [risk.description for risk in metadata.risks] == ["Decision dependency"]
        assert [resource.title for resource in metadata.resources] == ["AWS Jira"]
        assert metadata.resources[0].source_kind == ResourceLinkSourceKind.connected_source
        assert metadata.resources[0].disabled is False

        empty_month_metadata = await service.get_partner_metadata(
            cycle="2026-09",
            partner_id=partner_a.partner_id,
        )
        assert empty_month_metadata.status is None
        assert empty_month_metadata.risks == []
        assert empty_month_metadata.resources

        await cleanup_test_records(session, [partner_a_name, partner_b_name], [presenter_email])
        await session.commit()


async def create_presenter_fixture(
    session: AsyncSession,
    *,
    presenter_email: str,
    partner_a_name: str,
    partner_b_name: str,
    topic_label: str,
    cycle_month: date = date(2026, 8, 1),
) -> tuple[User, Partner, Partner]:
    presenter = User(email=presenter_email, display_name="Presenter User")
    presenter.role_assignments = [UserRoleAssignment(role_type=RoleType.presenter)]
    partner_a = Partner(
        name=partner_a_name,
        description="AWS partner",
        status=PartnerStatus.active.value,
    )
    partner_b = Partner(
        name=partner_b_name,
        description="Uber partner",
        status=PartnerStatus.active.value,
    )
    session.add_all([presenter, partner_a, partner_b])
    await session.flush()

    now = datetime.now(UTC)
    session.add_all(
        [
            PartnerUpdate(
                partner_id=partner_a.partner_id,
                cycle_month=cycle_month,
                title="Release decision needed",
                summary="Partner release validation needs a decision this month.",
                source_type="jira",
                source_label="AWS-501",
                source_url="https://jira.example.com/browse/AWS-501",
                status=PartnerUpdateStatus.approved.value,
                approved_by=presenter.user_id,
                approved_at=now,
                created_at=now,
                updated_at=now,
            ),
            PartnerUpdate(
                partner_id=partner_b.partner_id,
                cycle_month=cycle_month,
                title="Slack milestone update",
                summary="Partner milestone remains on track.",
                source_type="slack",
                source_label="#partner",
                source_url="https://slack.example.com/archives/C123",
                status=PartnerUpdateStatus.approved.value,
                approved_by=presenter.user_id,
                approved_at=now,
                created_at=now,
                updated_at=now,
            ),
            TopicUpdate(
                topic_label=topic_label,
                cycle_month=cycle_month,
                title="Cloud Marketing Initiatives Tracked here",
                summary=(
                    '<p><a href="https://example.com/marketing" target="_blank" '
                    'rel="noopener noreferrer">Cloud Marketing Initiatives Tracked here</a></p>'
                ),
                source_type="file",
                source_label="Monthly report",
                source_url="https://example.com/marketing",
                status=TopicUpdateStatus.approved.value,
                approved_by=presenter.user_id,
                approved_at=now,
                created_by=presenter.user_id,
                created_at=now,
                updated_at=now,
            ),
            PartnerUpdate(
                partner_id=partner_a.partner_id,
                cycle_month=cycle_month,
                title="Unapproved draft",
                summary="This should not appear to presenters.",
                source_type="manual",
                status=PartnerUpdateStatus.pending.value,
                created_at=now,
                updated_at=now,
            ),
        ]
    )

    snapshot = PartnerMetadataSnapshot(
        partner_id=partner_a.partner_id,
        cycle_month=cycle_month,
        status="amber",
        highlights_status="Release validation needs attention.",
        business_priority="High",
        goals="Close partner decision.",
        saved_by=presenter.user_id,
        saved_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(snapshot)
    await session.flush()
    session.add(
        PartnerMetadataRisk(
            metadata_id=snapshot.metadata_id,
            sort_order=0,
            description="Decision dependency",
            green_action="Confirm owner",
            severity="amber",
            assigned_to="Presenter",
            ramification="Could delay launch messaging.",
        )
    )
    session.add(
        PartnerResourceLink(
            partner_id=partner_a.partner_id,
            title="AWS Jira",
            url="https://jira.example.com/browse/AWS-501",
            description="Connected ticket",
            source_kind=ResourceLinkSourceKind.connected_source.value,
            created_by=presenter.user_id,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        PartnerResourceLink(
            partner_id=partner_a.partner_id,
            title="Archived AWS Jira",
            url="https://jira.example.com/browse/AWS-502",
            description="Disabled connected ticket",
            source_kind=ResourceLinkSourceKind.connected_source.value,
            created_by=presenter.user_id,
            created_at=now,
            updated_at=now,
            archived_at=now,
        )
    )
    await session.commit()
    return presenter, partner_a, partner_b


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
    await session.execute(delete(PartnerUpdate).where(PartnerUpdate.partner_id.in_(partner_ids)))
    await session.execute(
        delete(TopicUpdate).where(TopicUpdate.created_by.in_(select_user_ids(emails)))
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
