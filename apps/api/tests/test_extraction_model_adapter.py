import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.agents.extraction import (
    ExtractionOutputValidationError,
    SourceEventExtractionOrchestrator,
    build_source_event_model_request,
    normalize_source_event_extraction_mode,
)
from app.agents.extraction.model_adapter import ModelAdapterOutputError, parse_model_json
from app.agents.extraction.orchestrator import build_source_event_extraction_input
from app.agents.rulebooks import RulebookLoader
from app.core.config import Settings
from app.db.models.source_event import SourceEvent, SourcePayload


def settings_with(**overrides: object) -> Settings:
    settings = Settings()
    return settings.model_copy(update=overrides)


def test_model_request_includes_structured_payload_and_output_contract() -> None:
    source_event = make_source_event(
        source_type="jira_issue",
        technical_metadata={"issue_key": "AWS-123", "changed_fields": ["status"]},
    )
    source_payload = SourcePayload(
        source_event_id=source_event.source_event_id,
        raw_payload_json={"source_item": {"text": "Partner milestone moved to September."}},
        raw_text_encrypted="encrypted text reference only",
        retention_policy="structured_payload",
    )
    rulebook = RulebookLoader().load("source_event.jira")

    request = build_source_event_model_request(
        extraction_input=build_source_event_extraction_input(source_event, source_payload),
        rulebook=rulebook,
    )

    assert request["application"] == "Cloud AI Software Ecosystem Updates"
    assert request["mode"] == "dry_run_validation"
    assert request["rulebook"]["name"] == "source_event.jira"
    assert request["output_contract"]["decision"] == ["ignore", "create_update"]
    optional_fields = request["output_contract"]["create_update"]["draft_update_optional_fields"]
    assert "cycle_month" in optional_fields
    assert any(
        "Extract only net-new facts" in constraint for constraint in request["hard_constraints"]
    )
    assert any(
        "Do not treat acknowledgements" in constraint for constraint in request["hard_constraints"]
    )
    assert any(
        "Do not extract facts from acknowledgement clauses" in constraint
        for constraint in request["hard_constraints"]
    )
    assert any(
        "Do not join update clauses with semicolons" in constraint
        for constraint in request["hard_constraints"]
    )
    assert request["input"]["payload"]["payload_available"] is True
    assert request["input"]["payload"]["has_structured_payload"] is True
    assert request["input"]["payload"]["structured_payload"] == {
        "source_item": {"text": "Partner milestone moved to September."}
    }
    assert "encrypted text reference only" not in str(request)


@pytest.mark.asyncio
async def test_dry_run_ignore_output_is_recorded_without_creating_updates() -> None:
    orchestrator = SourceEventExtractionOrchestrator(
        settings=settings_with(ai_source_event_extraction_mode="dry_run"),
        model_adapter=FakeModelAdapter(
            {
                "decision": "ignore",
                "ignore_reason": "Formatting-only activity with no partner signal.",
            }
        ),
    )

    result = await orchestrator.extract(make_source_event(source_type="jira_issue"), None)
    output = result.to_agent_output()

    assert result.pending_updates_created == 0
    assert result.extraction_mode == "model_dry_run"
    assert result.model_name == "fake-update-extraction-model"
    assert output["model_output_validated"] is True
    assert output["model_decision"] == "ignore"
    assert output["ignore_reason"] == "Formatting-only activity with no partner signal."
    assert "draft_update_preview" not in output


@pytest.mark.asyncio
async def test_dry_run_create_output_records_preview_without_creating_updates() -> None:
    source_event = make_source_event(source_type="jira_issue")
    orchestrator = SourceEventExtractionOrchestrator(
        settings=settings_with(ai_source_event_extraction_mode="dry_run"),
        model_adapter=FakeModelAdapter(
            {
                "decision": "create_update",
                "draft_update": {
                    "title": "AWS validation moved to review",
                    "summary": "The linked Jira event indicates validation is ready for review.",
                    "source_label": "AWS-123",
                    "source_url": "https://jira.example.com/browse/AWS-123",
                    "reasoning_category": "status_change",
                    "confidence": 0.86,
                    "needs_human_attention": True,
                    "event_importance": "high",
                    "dedupe_key_hint": "AWS-123:status-review",
                },
            }
        ),
    )

    result = await orchestrator.extract(source_event, None)
    output = result.to_agent_output()

    assert result.pending_updates_created == 0
    assert output["model_decision"] == "create_update"
    assert output["draft_update_preview"] == {
        "partner_id": str(source_event.partner_id),
        "cycle_month": "2026-08-01",
        "title": "AWS validation moved to review",
        "summary": (
            "<ul><li>The linked Jira event indicates validation is ready for review.</li></ul>"
        ),
        "source_type": "jira",
        "source_label": "AWS-123",
        "source_url": "https://jira.example.com/browse/AWS-123",
        "source_event_key": source_event.idempotency_key,
        "connected_source_id": str(source_event.connected_source_id),
        "source_event_id": str(source_event.source_event_id),
        "reasoning_category": "status_change",
        "confidence": 0.86,
        "needs_human_attention": True,
        "event_importance": "high",
        "dedupe_key_hint": "AWS-123:status-review",
    }
    assert "Pending update creation remains disabled" in output["reason"]


@pytest.mark.asyncio
async def test_model_write_create_output_returns_pending_update_command() -> None:
    source_event = make_source_event(source_type="jira_issue")
    orchestrator = SourceEventExtractionOrchestrator(
        settings=settings_with(ai_source_event_extraction_mode="model_write"),
        model_adapter=FakeModelAdapter(
            {
                "decision": "create_update",
                "draft_update": {
                    "title": "AWS validation moved to review",
                    "summary": "AWS validation moved to review.\n2 partner tasks remain.",
                    "cycle_month": "2026-07-01",
                    "source_label": "AWS-123",
                    "source_url": "https://jira.example.com/browse/AWS-123",
                    "reasoning_category": "progress",
                    "confidence": 0.91,
                    "needs_human_attention": False,
                    "event_importance": "medium",
                    "dedupe_key_hint": "AWS-123:review",
                },
            }
        ),
    )

    result = await orchestrator.extract(source_event, None)
    output = result.to_agent_output()

    assert result.pending_updates_created == 0
    assert output["extraction_mode"] == "model_write"
    assert output["model_decision"] == "create_update"
    assert output["pending_update_command"] == {
        "partner_id": str(source_event.partner_id),
        "cycle_month": "2026-07-01",
        "title": "AWS validation moved to review",
        "summary": (
            "<ul><li>AWS validation moved to review.</li><li>2 partner tasks remain.</li></ul>"
        ),
        "source_type": "jira",
        "source_label": "AWS-123",
        "source_url": "https://jira.example.com/browse/AWS-123",
        "source_event_key": source_event.idempotency_key,
        "connected_source_id": str(source_event.connected_source_id),
        "source_event_id": str(source_event.source_event_id),
        "reasoning_category": "progress",
        "confidence": 0.91,
        "needs_human_attention": False,
        "event_importance": "medium",
        "dedupe_key_hint": "AWS-123:review",
    }


@pytest.mark.asyncio
async def test_model_write_ignore_output_returns_no_pending_update_command() -> None:
    orchestrator = SourceEventExtractionOrchestrator(
        settings=settings_with(ai_source_event_extraction_mode="model_write"),
        model_adapter=FakeModelAdapter(
            {
                "decision": "ignore",
                "ignore_reason": "Acknowledgement-only activity.",
            }
        ),
    )

    result = await orchestrator.extract(make_source_event(source_type="slack_channel"), None)
    output = result.to_agent_output()

    assert output["extraction_mode"] == "model_write"
    assert output["model_decision"] == "ignore"
    assert output["pending_updates_created"] == 0
    assert "pending_update_command" not in output


@pytest.mark.asyncio
async def test_dry_run_invalid_output_fails_closed() -> None:
    orchestrator = SourceEventExtractionOrchestrator(
        settings=settings_with(ai_source_event_extraction_mode="dry_run"),
        model_adapter=FakeModelAdapter({"decision": "create_update"}),
    )

    with pytest.raises(ExtractionOutputValidationError, match="create_update"):
        await orchestrator.extract(make_source_event(source_type="jira_issue"), None)


def test_extraction_mode_normalization_rejects_unknown_modes() -> None:
    assert normalize_source_event_extraction_mode("model-dry-run") == "model_dry_run"
    assert normalize_source_event_extraction_mode("model-write") == "model_write"

    with pytest.raises(ValueError, match="AI_SOURCE_EVENT_EXTRACTION_MODE"):
        normalize_source_event_extraction_mode("auto_create")


def test_model_json_parser_requires_json_object() -> None:
    assert parse_model_json('{"decision": "ignore"}') == {"decision": "ignore"}

    with pytest.raises(ModelAdapterOutputError, match="invalid JSON"):
        parse_model_json("not json")

    with pytest.raises(ModelAdapterOutputError, match="JSON object"):
        parse_model_json("[]")


class FakeModelAdapter:
    model_name = "fake-update-extraction-model"

    def __init__(self, output: dict[str, Any]) -> None:
        self.output = output

    async def extract(
        self,
        *,
        extraction_input: Any,
        rulebook: Any,
    ) -> dict[str, Any]:
        return self.output


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
        technical_metadata=technical_metadata or {"source": source_type},
    )
