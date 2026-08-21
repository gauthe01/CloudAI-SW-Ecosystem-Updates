import asyncio
import json
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
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateSourceType, PartnerUpdateStatus
from app.db.models.topic_update import TopicUpdate, TopicUpdateStatus
from app.db.session import get_session_factory
from app.domains.presenter import service as presenter_service
from app.domains.presenter.service import (
    PresenterService,
    build_executive_summary_payload,
    build_presenter_ask_payload,
    cached_presenter_ask_model_content,
    parse_decision_board_response,
    parse_presenter_ask_answer,
)


class FakeDecisionBoardRuntime:
    def __init__(self, client) -> None:
        self.client = client


class FakeDecisionBoardClient:
    def __init__(self, content: str) -> None:
        self.chat = FakeDecisionBoardChat(self)
        self.content = content
        self.calls = 0


class FakeDecisionBoardChat:
    def __init__(self, parent: FakeDecisionBoardClient) -> None:
        self.completions = FakeDecisionBoardCompletions(parent)


class FakeDecisionBoardCompletions:
    def __init__(self, parent: FakeDecisionBoardClient) -> None:
        self.parent = parent

    async def create(self, **_kwargs):
        self.parent.calls += 1
        await asyncio.sleep(0)
        return FakeDecisionBoardResponse(self.parent.content)


class FakeDecisionBoardResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeDecisionBoardChoice(content)]


class FakeDecisionBoardChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeDecisionBoardMessage(content)


class FakeDecisionBoardMessage:
    def __init__(self, content: str) -> None:
        self.content = content


def test_decision_board_parser_accepts_interview_card_shape() -> None:
    update_id = uuid.uuid4()
    payload = f"""
    {{
      "signals": [
        {{
          "partner_id": "{uuid.uuid4()}",
          "partner_name": "SAP HANA Cloud",
          "priority": "P3",
          "title": "ARM64 publishing automation monitoring",
          "update_line": "ARM64 image publishing automation needs monitoring.",
          "action": null,
          "source_kind": "approved_update",
          "update_id": "{update_id}"
        }},
        {{
          "partner_name": "AWS",
          "priority": "P2",
          "title": "Legal agreement delay",
          "update_line": "Legal agreement delay is marked amber and could delay launch messaging.",
          "action": "Confirm campaign input owner",
          "source_kind": "metadata_risk",
          "metadata_risk_id": "{uuid.uuid4()}"
        }}
      ],
      "source_note": null
    }}
    """

    parsed = parse_decision_board_response(payload)

    signals = parsed["signals"]
    assert len(signals) == 2
    assert signals[0].title == "ARM64 publishing automation monitoring"
    assert signals[0].update_line == "ARM64 image publishing automation needs monitoring."
    assert signals[0].action is None
    assert signals[0].update_id == update_id
    assert signals[1].action == "Confirm campaign input owner"


def test_decision_board_parser_preserves_more_than_fifteen_cards() -> None:
    raw_signals = [
        {
            "partner_id": str(uuid.uuid4()),
            "partner_name": f"Partner {index}",
            "priority": "P2",
            "title": f"Action item {index}",
            "update_line": f"Action item {index} needs presenter attention.",
            "source_kind": "approved_update",
        }
        for index in range(20)
    ]

    parsed = parse_decision_board_response(
        json.dumps({"signals": raw_signals, "source_note": None})
    )

    assert len(parsed["signals"]) == 20


def test_executive_summary_payload_excludes_source_fields() -> None:
    update = presenter_service.PresenterUpdateResponse(
        update_id=uuid.uuid4(),
        partner_id=uuid.uuid4(),
        partner_name="Google",
        scope="partner",
        topic_label=None,
        cycle="2026-04",
        title="Cloud Next planning",
        summary=(
            "Google Cloud Next is planned for April 21-23 with Arm booth demos "
            "and customer workshop."
        ),
        source_type=PartnerUpdateSourceType.email,
        source_label="Source",
        source_url="https://example.com/source",
        approved_at=None,
        approved_by=None,
    )

    payload = build_executive_summary_payload(
        cycle="2026-04",
        date_start=None,
        date_end=None,
        scoped_partner_ids=[],
        updates=[update],
        rulebook_body="Do not include source links.",
        rulebook_trace_version="active:test",
    )

    approved_update = payload["approved_updates"][0]
    assert "source_label" not in approved_update
    assert "source_url" not in approved_update
    assert "approved_at" not in approved_update
    assert approved_update["partner_name"] == "Google"
    assert "April 21-23" in approved_update["summary"]


def test_presenter_ask_payload_uses_focused_update_and_metadata_evidence() -> None:
    partner_id = uuid.uuid4()
    relevant_update = presenter_service.PresenterUpdateResponse(
        update_id=uuid.uuid4(),
        partner_id=partner_id,
        partner_name="Google",
        scope="partner",
        topic_label=None,
        cycle="2026-04",
        title="Cloud Next planning",
        summary="Cloud Next is planned for April 21-23 with customer workshops.",
        source_type=PartnerUpdateSourceType.email,
        source_label=None,
        source_url=None,
        approved_at=None,
        approved_by=None,
    )
    irrelevant_update = presenter_service.PresenterUpdateResponse(
        update_id=uuid.uuid4(),
        partner_id=uuid.uuid4(),
        partner_name="Redis",
        scope="partner",
        topic_label=None,
        cycle="2026-04",
        title="Benchmark result",
        summary="Vector search benchmark completed.",
        source_type=PartnerUpdateSourceType.manual,
        source_label=None,
        source_url=None,
        approved_at=None,
        approved_by=None,
    )

    payload = build_presenter_ask_payload(
        question="What is coming up next month for Google?",
        cycle="2026-04",
        date_start=None,
        date_end=None,
        scoped_partner_ids=[partner_id],
        intent="lookahead",
        updates=[relevant_update, irrelevant_update],
        metadata_context=[
            {
                "partner_id": str(partner_id),
                "partner_name": "Google",
                "cycle": "2026-04",
                "status": "green",
                "goals": "Prepare Cloud Next workshop.",
                "execution_timeline": "Customer workshop on April 22.",
                "risks": [
                    {
                        "metadata_risk_id": str(uuid.uuid4()),
                        "description": "Speaker confirmation pending.",
                        "green_action": "Confirm speakers by April 10.",
                    }
                ],
                "resources": [],
            }
        ],
        rulebook_body="Do not dump all evidence.",
        rulebook_trace_version="active:test",
    )

    evidence = payload["evidence"]
    assert len(evidence) < 4
    rendered = json.dumps(evidence)
    assert "Cloud Next" in rendered
    assert "Customer workshop" in rendered
    assert "_citation_catalog" in payload


def test_presenter_ask_parser_keeps_only_supplied_citations() -> None:
    citation = presenter_service.PresenterAskCitation(
        citation_id="approved_update:1",
        kind="approved_update",
        partner_name="Google",
        title="Cloud Next planning",
        summary="Cloud Next is planned.",
        cycle="2026-04",
    )
    parsed = parse_presenter_ask_answer(
        json.dumps(
            {
                "answer": "Google is preparing Cloud Next.",
                "confidence": "high",
                "bullets": ["Customer workshop is planned."],
                "citations": [
                    {"citation_id": "approved_update:1"},
                    {"citation_id": "approved_update:unknown"},
                ],
            }
        ),
        citation_catalog={"approved_update:1": citation},
    )

    assert parsed.answer == "Google is preparing Cloud Next."
    assert parsed.confidence == "high"
    assert parsed.bullets == ["Customer workshop is planned."]
    assert [item.citation_id for item in parsed.citations] == ["approved_update:1"]


@pytest.mark.asyncio
async def test_presenter_ask_model_content_is_cached_for_identical_payloads() -> None:
    presenter_service._PRESENTER_ASK_CONTENT_CACHE.clear()
    presenter_service._PRESENTER_ASK_IN_FLIGHT.clear()
    fake_client = FakeDecisionBoardClient(
        '{"answer":"Google is preparing Cloud Next.","confidence":"high","citations":[]}'
    )
    runtime = FakeDecisionBoardRuntime(fake_client)
    payload = {
        "task": "presenter_ask_ai",
        "question": "What changed this cycle?",
        "intent": "cycle_change",
        "scope": {"cycle": "2026-04", "partner_ids": []},
        "evidence": [{"citation_id": "approved_update:1", "text": "Cloud Next planned."}],
        "_citation_catalog": {},
    }

    first, second = await asyncio.gather(
        cached_presenter_ask_model_content(
            runtime=runtime,
            model="reporting-model",
            payload=payload,
        ),
        cached_presenter_ask_model_content(
            runtime=runtime,
            model="reporting-model",
            payload=payload,
        ),
    )
    third = await cached_presenter_ask_model_content(
        runtime=runtime,
        model="reporting-model",
        payload=payload,
    )

    assert first == second == third
    assert fake_client.calls == 1


@pytest.mark.asyncio
async def test_executive_summary_model_content_is_cached_for_identical_payloads() -> None:
    presenter_service._EXECUTIVE_SUMMARY_CONTENT_CACHE.clear()
    presenter_service._EXECUTIVE_SUMMARY_IN_FLIGHT.clear()
    fake_client = FakeDecisionBoardClient(
        '{"bullets":["Google: Cloud Next is planned for April 21-23."],"source_note":null}'
    )
    runtime = FakeDecisionBoardRuntime(fake_client)
    payload = {
        "task": "presenter_executive_summary",
        "scope": {"cycle": "2026-04", "partner_ids": []},
        "approved_updates": [
            {
                "update_id": str(uuid.uuid4()),
                "partner_id": str(uuid.uuid4()),
                "partner_name": "Google",
                "title": "Cloud Next planning",
                "summary": "Google Cloud Next is planned for April 21-23.",
            }
        ],
    }

    first, second = await asyncio.gather(
        presenter_service.cached_executive_summary_model_content(
            runtime=runtime,
            model="reporting-model",
            payload=payload,
        ),
        presenter_service.cached_executive_summary_model_content(
            runtime=runtime,
            model="reporting-model",
            payload=payload,
        ),
    )
    third = await presenter_service.cached_executive_summary_model_content(
        runtime=runtime,
        model="reporting-model",
        payload=payload,
    )

    assert first == second == third
    assert fake_client.calls == 1


@pytest.mark.asyncio
async def test_decision_board_model_content_is_cached_for_identical_payloads() -> None:
    presenter_service._DECISION_BOARD_CONTENT_CACHE.clear()
    presenter_service._DECISION_BOARD_IN_FLIGHT.clear()
    fake_client = FakeDecisionBoardClient(
        '{"signals":[],"source_note":"No Decision Board items found for the '
        'selected partners and period."}'
    )
    runtime = FakeDecisionBoardRuntime(fake_client)
    payload = {
        "task": "presenter_decision_board",
        "scope": {"cycle": "2026-07", "partner_ids": []},
        "approved_updates": [],
        "partner_metadata": [],
    }

    first, second = await asyncio.gather(
        presenter_service.cached_decision_board_model_content(
            runtime=runtime,
            model="reporting-model",
            payload=payload,
        ),
        presenter_service.cached_decision_board_model_content(
            runtime=runtime,
            model="reporting-model",
            payload=payload,
        ),
    )
    third = await presenter_service.cached_decision_board_model_content(
        runtime=runtime,
        model="reporting-model",
        payload=payload,
    )

    assert first == second == third
    assert fake_client.calls == 1


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
        assert email.subject == f"{partner_a_name} Monthly Update - August 2031"
        assert f"{partner_a_name}:" in email.body
        assert "Release decision needed" in email.body
        assert (
            "- Release decision needed: Partner release validation needs a decision this month."
            in email.body
        )
        assert partner_b_name not in email.body
        assert topic_label not in email.body

        all_partner_email = await service.draft_email(cycle=cycle)
        assert all_partner_email.subject == "Partner Ecosystem Monthly Update - August 2031"
        assert "Other Partners:" in all_partner_email.body
        assert f"{topic_label}:" in all_partner_email.body
        assert "- Cloud Marketing Initiatives Tracked here" in all_partner_email.body
        assert "<p>" not in all_partner_email.body
        assert "<a href=" not in all_partner_email.body
        assert "https://example.com/marketing" not in all_partner_email.body

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
