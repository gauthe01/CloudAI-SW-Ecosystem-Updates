import argparse
import asyncio
import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from openai import OpenAIError

from app.agents.extraction import SourceEventExtractionOrchestrator
from app.agents.runtime import (
    AIRuntimeConfigurationError,
    get_ai_runtime_config,
    normalize_ai_provider,
    require_ai_runtime_config,
)
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.models.source_event import SourceEvent

DEFAULT_SOURCE_TYPE = "jira_issue"
DEFAULT_SOURCE_URL = "https://example.com/probe/source-event"
DEFAULT_TECHNICAL_METADATA = {
    "probe": True,
    "event_kind": "controlled_ai_dry_run",
    "business_signal": (
        "Synthetic dry-run only. Validate JSON contract; do not create a partner update."
    ),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a controlled dry-run source-event extraction against the configured "
            "enterprise OpenAI-compatible endpoint."
        )
    )
    parser.add_argument(
        "--source-type",
        default=DEFAULT_SOURCE_TYPE,
        help="Source type rulebook to test, for example jira_issue or slack_channel.",
    )
    parser.add_argument(
        "--source-url",
        default=DEFAULT_SOURCE_URL,
        help="Synthetic source URL included in the model input envelope.",
    )
    parser.add_argument(
        "--technical-metadata-json",
        default=json.dumps(DEFAULT_TECHNICAL_METADATA, sort_keys=True),
        help="JSON object used as synthetic technical metadata.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON probe report.",
    )
    return parser.parse_args(argv)


async def run_probe(
    *,
    settings: Settings | None = None,
    source_type: str = DEFAULT_SOURCE_TYPE,
    source_url: str = DEFAULT_SOURCE_URL,
    technical_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_settings = settings or get_settings()
    require_ai_runtime_config(runtime_settings)
    probe_settings = runtime_settings.model_copy(
        update={"ai_source_event_extraction_mode": "dry_run"}
    )
    source_event = build_probe_source_event(
        source_type=source_type,
        source_url=source_url,
        technical_metadata=technical_metadata or DEFAULT_TECHNICAL_METADATA,
    )
    result = await SourceEventExtractionOrchestrator(settings=probe_settings).extract(
        source_event,
        None,
    )
    return {
        "status": "succeeded",
        "probe": "source_event_dry_run",
        "runtime": redacted_runtime_summary(runtime_settings),
        "result": result.to_agent_output(),
        "database_writes": {
            "source_events": 0,
            "source_payloads": 0,
            "partner_updates": 0,
        },
    }


def build_probe_source_event(
    *,
    source_type: str,
    source_url: str,
    technical_metadata: dict[str, Any],
) -> SourceEvent:
    source_event_id = uuid.uuid4()
    connected_source_id = uuid.uuid4()
    partner_id = uuid.uuid4()
    event_timestamp = datetime.now(UTC)
    idempotency_key = build_probe_idempotency_key(
        source_type=source_type,
        source_url=source_url,
        technical_metadata=technical_metadata,
        event_timestamp=event_timestamp,
    )
    return SourceEvent(
        source_event_id=source_event_id,
        connected_source_id=connected_source_id,
        partner_id=partner_id,
        source_type=source_type,
        external_event_id=f"dry-run-probe:{source_event_id}",
        idempotency_key=idempotency_key,
        source_url=source_url,
        source_event_timestamp=event_timestamp,
        technical_metadata=technical_metadata,
    )


def build_probe_idempotency_key(
    *,
    source_type: str,
    source_url: str,
    technical_metadata: dict[str, Any],
    event_timestamp: datetime,
) -> str:
    payload = {
        "source_type": source_type,
        "source_url": source_url,
        "technical_metadata": technical_metadata,
        "source_event_timestamp": event_timestamp.isoformat(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def parse_metadata_json(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("--technical-metadata-json must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("--technical-metadata-json must be a JSON object.")
    return parsed


def redacted_runtime_summary(settings: Settings) -> dict[str, Any]:
    config = get_ai_runtime_config(settings)
    provider = normalize_ai_provider(settings.ai_provider)
    return {
        "provider": provider,
        "base_url_configured": bool(config["base_url"]),
        "api_key_configured": bool(settings.ai_api_key),
        "update_extraction_model": config["update_extraction_model"],
        "timeout_seconds": config["timeout_seconds"],
        "max_retries": config["max_retries"],
        "ca_bundle_configured": bool(config["ca_bundle"]),
        "forced_extraction_mode": "dry_run",
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        report = asyncio.run(
            run_probe(
                settings=settings,
                source_type=args.source_type,
                source_url=args.source_url,
                technical_metadata=parse_metadata_json(args.technical_metadata_json),
            )
        )
    except (AIRuntimeConfigurationError, ValueError, OpenAIError) as exc:
        print(
            json.dumps(probe_failure_report(settings=settings, error=exc), sort_keys=True),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


def probe_failure_report(*, settings: Settings, error: Exception) -> dict[str, Any]:
    return {
        "status": "failed",
        "probe": "source_event_dry_run",
        "error_type": error.__class__.__name__,
        "error": str(error),
        "runtime": redacted_runtime_summary(settings),
        "next_action": next_action_for_error(error),
    }


def next_action_for_error(error: Exception) -> str:
    message = error_chain_text(error)
    if "CERTIFICATE_VERIFY_FAILED" in message or "certificate verify failed" in message:
        return (
            "Configure a corporate CA bundle inside the container and set "
            "AI_CA_BUNDLE=/app/certs/<ca-bundle>.pem."
        )
    if isinstance(error, AIRuntimeConfigurationError):
        return "Complete the required AI_PROVIDER, AI_BASE_URL, AI_API_KEY, and model settings."
    return "Review endpoint connectivity, credentials, model name, and response-format support."


def error_chain_text(error: BaseException) -> str:
    messages: list[str] = []
    current: BaseException | None = error
    while current is not None:
        messages.append(str(current))
        current = current.__cause__ or current.__context__
    return " | ".join(message for message in messages if message)


if __name__ == "__main__":
    raise SystemExit(main())
