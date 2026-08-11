import uuid
from datetime import UTC, datetime

import pytest

from app.agents.extraction import (
    SourceEventExtractionOrchestrator,
    source_event_rulebook_name,
)
from app.agents.extraction.orchestrator import build_source_event_extraction_input
from app.db.models.source_event import SourceEvent, SourcePayload


def test_source_event_rulebook_resolver_maps_supported_source_types() -> None:
    assert source_event_rulebook_name("jira_issue") == "source_event.jira"
    assert source_event_rulebook_name("slack_channel") == "source_event.slack"
    assert source_event_rulebook_name("sharepoint_file") == "source_event.sharepoint"
    assert source_event_rulebook_name("confluence_page") == "source_event.confluence"
    assert source_event_rulebook_name("github_repository") == "source_event.github"
    assert source_event_rulebook_name("github_issue") == "source_event.github"
    assert source_event_rulebook_name("github_pull_request") == "source_event.github"


def test_source_event_rulebook_resolver_rejects_unknown_source_type() -> None:
    with pytest.raises(ValueError, match="No source-event rulebook"):
        source_event_rulebook_name("unknown_source")


def test_source_event_extraction_input_keeps_payload_as_reference_only() -> None:
    source_event = make_source_event(
        source_type="jira_issue",
        technical_metadata={"issue_key": "AWS-123", "changed_fields": ["status"]},
    )
    source_payload = SourcePayload(
        source_event_id=source_event.source_event_id,
        raw_payload_json={"secret": "raw payload should not be copied to model payload"},
        raw_text_encrypted="encrypted text reference only",
        retention_policy="structured_payload",
    )

    extraction_input = build_source_event_extraction_input(source_event, source_payload)
    model_payload = extraction_input.to_model_payload()

    assert model_payload["technical_metadata"] == {
        "issue_key": "AWS-123",
        "changed_fields": ["status"],
    }
    assert model_payload["payload"]["payload_available"] is True
    assert model_payload["payload"]["has_structured_payload"] is True
    assert model_payload["payload"]["has_encrypted_text"] is True
    assert "raw payload should not be copied" not in str(model_payload)
    assert len(extraction_input.input_fingerprint) == 64


@pytest.mark.asyncio
async def test_source_event_orchestrator_returns_infrastructure_only_result() -> None:
    source_event = make_source_event(source_type="jira_issue")

    result = await SourceEventExtractionOrchestrator().extract(source_event, None)

    assert result.pending_updates_created == 0
    assert result.extraction_mode == "infrastructure_only"
    assert result.rulebook_name == "source_event.jira"
    assert result.rulebook_status == "production"
    assert result.model_name is None
    assert "Feature 23B/23C" in result.reason


def make_source_event(
    *,
    source_type: str,
    technical_metadata: dict | None = None,
) -> SourceEvent:
    return SourceEvent(
        source_event_id=uuid.uuid4(),
        connected_source_id=uuid.uuid4(),
        partner_id=uuid.uuid4(),
        source_type=source_type,
        external_event_id="external-event",
        idempotency_key=f"{source_type}:event",
        source_url="https://example.com/source",
        source_event_timestamp=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        technical_metadata=technical_metadata,
    )
