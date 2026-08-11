import uuid
from datetime import UTC, datetime

import pytest

from app.agents.extraction import (
    ExtractionDecision,
    ExtractionImportance,
    ExtractionOutputValidationError,
    pending_update_command_from_model_output,
    validate_source_event_model_output,
)
from app.db.models.partner_update import PartnerUpdateSourceType
from app.db.models.source_event import SourceEvent


def test_valid_ignore_output_does_not_create_pending_update_command() -> None:
    output = validate_source_event_model_output(
        {
            "decision": "ignore",
            "ignore_reason": "Formatting-only change with no business impact.",
        }
    )

    command = pending_update_command_from_model_output(
        source_event=make_source_event(source_type="jira_issue"),
        model_output=output,
    )

    assert output.decision == ExtractionDecision.ignore
    assert command is None


def test_valid_create_output_converts_to_pending_update_command() -> None:
    source_event = make_source_event(source_type="jira_issue")
    output = validate_source_event_model_output(
        {
            "decision": "create_update",
            "draft_update": {
                "title": " AWS validation moved to partner review ",
                "summary": (
                    " The Jira ticket now shows validation ready for review.\n"
                    "See https://jira.example.com/browse/AWS-123 "
                ),
                "cycle_month": "2026-07-01",
                "source_label": " AWS-123 ",
                "source_url": "https://jira.example.com/browse/AWS-123",
                "reasoning_category": "status_change",
                "confidence": 0.82,
                "needs_human_attention": True,
                "event_importance": "high",
                "dedupe_key_hint": "AWS-123:status-review",
            },
        }
    )

    command = pending_update_command_from_model_output(
        source_event=source_event,
        model_output=output,
    )

    assert command is not None
    assert command.partner_id == source_event.partner_id
    assert command.cycle_month.isoformat() == "2026-07-01"
    assert command.title == "AWS validation moved to partner review"
    assert command.summary == (
        "<ul>"
        "<li>The Jira ticket now shows validation ready for review.</li>"
        '<li>See <a href="https://jira.example.com/browse/AWS-123">'
        "https://jira.example.com/browse/AWS-123</a></li>"
        "</ul>"
    )
    assert command.source_type == PartnerUpdateSourceType.jira
    assert command.source_label == "AWS-123"
    assert command.source_url == "https://jira.example.com/browse/AWS-123"
    assert command.source_event_key == source_event.idempotency_key
    assert command.connected_source_id == source_event.connected_source_id
    assert command.source_event_id == source_event.source_event_id
    assert command.reasoning_category == "status_change"
    assert command.confidence == 0.82
    assert command.needs_human_attention is True
    assert command.event_importance == ExtractionImportance.high
    assert command.dedupe_key_hint == "AWS-123:status-review"


def test_semicolon_joined_plain_text_summary_splits_into_bullets() -> None:
    source_event = make_source_event(source_type="jira_issue")
    output = validate_source_event_model_output(
        {
            "decision": "create_update",
            "draft_update": {
                "title": "SAP AGI CPU evaluation",
                "summary": (
                    "SAP's AGI CPU evaluation is starting while legal teams "
                    "work through equipment loan and collaboration agreements; "
                    "current timeline may provide SAP with a CRB in Aug./Sept. "
                    "and 4 QS A1 systems for performance benchmarking in October."
                ),
                "confidence": 0.9,
            },
        }
    )

    command = pending_update_command_from_model_output(
        source_event=source_event,
        model_output=output,
    )

    assert command is not None
    assert command.summary == (
        "<ul>"
        "<li>SAP&#x27;s AGI CPU evaluation is starting while legal teams work through "
        "equipment loan and collaboration agreements</li>"
        "<li>current timeline may provide SAP with a CRB in Aug./Sept. and 4 QS A1 "
        "systems for performance benchmarking in October.</li>"
        "</ul>"
    )


def test_semicolon_joined_html_summary_splits_into_bullets() -> None:
    source_event = make_source_event(source_type="jira_issue")
    output = validate_source_event_model_output(
        {
            "decision": "create_update",
            "draft_update": {
                "title": "SAP AGI CPU evaluation",
                "summary": (
                    "<ul><li>SAP's AGI CPU evaluation is starting; current timeline "
                    "may provide SAP with a CRB in Aug./Sept.</li></ul>"
                ),
                "confidence": 0.9,
            },
        }
    )

    command = pending_update_command_from_model_output(
        source_event=source_event,
        model_output=output,
    )

    assert command is not None
    assert command.summary == (
        "<ul>"
        "<li>SAP's AGI CPU evaluation is starting</li>"
        "<li>current timeline may provide SAP with a CRB in Aug./Sept.</li>"
        "</ul>"
    )


def test_placeholder_source_label_falls_back_to_source_metadata() -> None:
    source_event = make_source_event(source_type="jira_issue")
    source_event.technical_metadata = {
        "issue_summary": "SVE Developer Content/Training Course to address SAP Hana feedback"
    }
    output = validate_source_event_model_output(
        {
            "decision": "create_update",
            "draft_update": {
                "title": "Action request",
                "summary": "Target dates requested.",
                "source_label": "Jira link title",
                "confidence": 0.0,
            },
        }
    )

    command = pending_update_command_from_model_output(
        source_event=source_event,
        model_output=output,
    )

    assert command is not None
    assert (
        command.source_label
        == "SVE Developer Content/Training Course to address SAP Hana feedback"
    )


def test_generic_jira_key_source_label_falls_back_to_source_metadata() -> None:
    source_event = make_source_event(source_type="jira_issue")
    source_event.technical_metadata = {
        "source_items": [
            {
                "type": "issue_summary",
                "text": "SVE Developer Content/Training Course to address SAP Hana feedback",
            }
        ]
    }
    output = validate_source_event_model_output(
        {
            "decision": "create_update",
            "draft_update": {
                "title": "Progress update",
                "summary": "Course material is in review.",
                "source_label": "Jira STESOL-431",
                "confidence": 0.8,
            },
        }
    )

    command = pending_update_command_from_model_output(
        source_event=source_event,
        model_output=output,
    )

    assert command is not None
    assert (
        command.source_label
        == "SVE Developer Content/Training Course to address SAP Hana feedback"
    )


def test_create_output_requires_draft_update() -> None:
    with pytest.raises(ExtractionOutputValidationError, match="create_update"):
        validate_source_event_model_output({"decision": "create_update"})


def test_create_output_rejects_non_month_start_cycle_month() -> None:
    with pytest.raises(ExtractionOutputValidationError, match="cycle_month"):
        validate_source_event_model_output(
            {
                "decision": "create_update",
                "draft_update": {
                    "title": "Invalid cycle month",
                    "summary": "Cycle month must be month-start.",
                    "cycle_month": "2026-07-15",
                    "confidence": 0.8,
                },
            }
        )


def test_ignore_output_rejects_draft_update() -> None:
    with pytest.raises(ExtractionOutputValidationError, match="must not include"):
        validate_source_event_model_output(
            {
                "decision": "ignore",
                "ignore_reason": "No useful signal.",
                "draft_update": {
                    "title": "Should not exist",
                    "summary": "Ignore decisions cannot also create updates.",
                    "confidence": 0.5,
                },
            }
        )


def test_output_rejects_unexpected_fields_and_invalid_confidence() -> None:
    with pytest.raises(ExtractionOutputValidationError, match="Extra inputs"):
        validate_source_event_model_output(
            {
                "decision": "ignore",
                "ignore_reason": "No useful signal.",
                "unexpected": "field",
            }
        )

    with pytest.raises(ExtractionOutputValidationError, match="less than or equal"):
        validate_source_event_model_output(
            {
                "decision": "create_update",
                "draft_update": {
                    "title": "Invalid confidence",
                    "summary": "Confidence must be a bounded score.",
                    "confidence": 1.5,
                },
            }
        )


def test_pending_update_command_rejects_unsupported_source_type() -> None:
    output = validate_source_event_model_output(
        {
            "decision": "create_update",
            "draft_update": {
                "title": "Valid draft",
                "summary": "Valid summary.",
                "confidence": 0.8,
            },
        }
    )

    with pytest.raises(ExtractionOutputValidationError, match="unsupported source type"):
        pending_update_command_from_model_output(
            source_event=make_source_event(source_type="unknown_source"),
            model_output=output,
        )


def make_source_event(*, source_type: str) -> SourceEvent:
    return SourceEvent(
        source_event_id=uuid.uuid4(),
        connected_source_id=uuid.uuid4(),
        partner_id=uuid.uuid4(),
        source_type=source_type,
        external_event_id="external-event",
        idempotency_key=f"{source_type}:event",
        source_url="https://example.com/source",
        source_event_timestamp=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        technical_metadata={"source": source_type},
    )
