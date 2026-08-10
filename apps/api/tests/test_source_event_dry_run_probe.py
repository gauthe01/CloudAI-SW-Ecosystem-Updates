from datetime import UTC, datetime

import pytest

from app.agents.runtime import AIRuntimeConfigurationError
from app.core.config import Settings
from app.tools.source_event_dry_run_probe import (
    build_probe_idempotency_key,
    build_probe_source_event,
    error_chain_text,
    next_action_for_error,
    parse_metadata_json,
    probe_failure_report,
    redacted_runtime_summary,
    run_probe,
)


def settings_with(**overrides: object) -> Settings:
    settings = Settings()
    return settings.model_copy(update=overrides)


def test_probe_source_event_is_in_memory_and_has_valid_identity() -> None:
    source_event = build_probe_source_event(
        source_type="jira_issue",
        source_url="https://jira.example.com/browse/AWS-123",
        technical_metadata={"probe": True},
    )

    assert source_event.source_event_id is not None
    assert source_event.connected_source_id is not None
    assert source_event.partner_id is not None
    assert source_event.source_type == "jira_issue"
    assert source_event.source_url == "https://jira.example.com/browse/AWS-123"
    assert source_event.technical_metadata == {"probe": True}
    assert len(source_event.idempotency_key) == 64


def test_probe_idempotency_key_is_stable_for_same_payload() -> None:
    timestamp = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)

    key_a = build_probe_idempotency_key(
        source_type="jira_issue",
        source_url="https://jira.example.com/browse/AWS-123",
        technical_metadata={"probe": True},
        event_timestamp=timestamp,
    )
    key_b = build_probe_idempotency_key(
        source_type="jira_issue",
        source_url="https://jira.example.com/browse/AWS-123",
        technical_metadata={"probe": True},
        event_timestamp=timestamp,
    )

    assert key_a == key_b


def test_parse_metadata_json_requires_object() -> None:
    assert parse_metadata_json('{"probe": true}') == {"probe": True}

    with pytest.raises(ValueError, match="valid JSON"):
        parse_metadata_json("not json")

    with pytest.raises(ValueError, match="JSON object"):
        parse_metadata_json("[]")


def test_redacted_runtime_summary_does_not_expose_secret_values() -> None:
    settings = settings_with(
        ai_provider="enterprise_openai_compatible",
        ai_base_url="https://enterprise.example.com/v1",
        ai_api_key="secret-key",
        ai_model_update_extraction="updates-model",
        ai_ca_bundle="/etc/ssl/certs/enterprise.pem",
    )

    summary = redacted_runtime_summary(settings)

    assert summary["provider"] == "enterprise_openai_compatible"
    assert summary["base_url_configured"] is True
    assert summary["api_key_configured"] is True
    assert summary["ca_bundle_configured"] is True
    assert summary["update_extraction_model"] == "updates-model"
    assert "secret-key" not in str(summary)
    assert "https://enterprise.example.com/v1" not in str(summary)


@pytest.mark.asyncio
async def test_probe_requires_ai_runtime_configuration() -> None:
    with pytest.raises(AIRuntimeConfigurationError, match="disabled"):
        await run_probe(settings=settings_with(ai_provider="disabled"))


def test_probe_failure_report_gives_certificate_next_action() -> None:
    settings = settings_with(
        ai_provider="enterprise_openai_compatible",
        ai_base_url="https://enterprise.example.com/v1",
        ai_api_key="secret-key",
        ai_model_update_extraction="updates-model",
    )
    error = RuntimeError("certificate verify failed: CERTIFICATE_VERIFY_FAILED")

    report = probe_failure_report(settings=settings, error=error)

    assert report["status"] == "failed"
    assert report["error_type"] == "RuntimeError"
    assert "AI_CA_BUNDLE=/app/certs/" in report["next_action"]
    assert "secret-key" not in str(report)
    assert "https://enterprise.example.com/v1" not in str(report)


def test_next_action_for_config_error_is_specific() -> None:
    action = next_action_for_error(AIRuntimeConfigurationError("AI runtime is disabled."))

    assert "AI_PROVIDER" in action


def test_next_action_detects_certificate_error_from_exception_chain() -> None:
    inner = RuntimeError("certificate verify failed: unable to get local issuer certificate")
    outer = RuntimeError("Connection error.")
    outer.__cause__ = inner

    assert "certificate verify failed" in error_chain_text(outer)
    assert "AI_CA_BUNDLE=/app/certs/" in next_action_for_error(outer)
