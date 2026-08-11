import json
from typing import TYPE_CHECKING, Any, Protocol

from app.agents.rulebooks import Rulebook
from app.agents.runtime.client import AIClientRuntime

if TYPE_CHECKING:
    from app.agents.extraction.orchestrator import SourceEventExtractionInput


class ModelAdapterOutputError(ValueError):
    """Raised when a model response cannot be parsed into candidate JSON."""


class SourceEventModelAdapter(Protocol):
    @property
    def model_name(self) -> str:
        """Name of the model used by the adapter."""

    async def extract(
        self,
        *,
        extraction_input: "SourceEventExtractionInput",
        rulebook: Rulebook,
    ) -> dict[str, Any]:
        """Return raw JSON-like output for validation by the extraction contract."""


class OpenAISourceEventModelAdapter:
    def __init__(
        self,
        *,
        runtime: AIClientRuntime,
        max_output_tokens: int,
    ) -> None:
        self.runtime = runtime
        self.max_output_tokens = max_output_tokens

    @property
    def model_name(self) -> str:
        return self.runtime.update_extraction_model

    async def extract(
        self,
        *,
        extraction_input: "SourceEventExtractionInput",
        rulebook: Rulebook,
    ) -> dict[str, Any]:
        response = await self.runtime.client.chat.completions.create(
            model=self.runtime.update_extraction_model,
            messages=[
                {"role": "system", "content": source_event_extraction_system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        build_source_event_model_request(
                            extraction_input=extraction_input,
                            rulebook=rulebook,
                        ),
                        sort_keys=True,
                        default=str,
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=self.max_output_tokens,
        )
        content = response.choices[0].message.content
        if not content:
            raise ModelAdapterOutputError("Model returned an empty extraction response.")
        return parse_model_json(content)


def build_source_event_model_request(
    *,
    extraction_input: "SourceEventExtractionInput",
    rulebook: Rulebook,
) -> dict[str, Any]:
    return {
        "application": "Cloud AI Software Ecosystem Updates",
        "task": "source_event_extraction",
        "mode": "dry_run_validation",
        "rulebook": {
            "name": rulebook.name,
            "trace_version": rulebook.trace_version,
            "status": rulebook.status,
            "body": rulebook.body,
        },
        "input": extraction_input.to_model_payload(),
        "output_contract": {
            "decision": ["ignore", "create_update"],
            "ignore": {
                "required_fields": ["decision", "ignore_reason"],
                "forbidden_fields": ["draft_update"],
            },
            "create_update": {
                "required_fields": ["decision", "draft_update"],
                "draft_update_required_fields": ["title", "summary", "confidence"],
                "draft_update_optional_fields": [
                    "cycle_month",
                    "source_label",
                    "source_url",
                    "reasoning_category",
                    "needs_human_attention",
                    "event_importance",
                    "dedupe_key_hint",
                ],
            },
        },
        "hard_constraints": [
            "Return JSON only.",
            "Do not include fields outside the output contract.",
            "Use create_update only when the source event contains a partner-relevant update.",
            (
                "Use ignore when the event is noise, access-only, formatting-only, "
                "or not business relevant."
            ),
            "Never invent facts not present in the provided input or rulebook.",
            (
                "When a source item has its own timestamp, set draft_update.cycle_month "
                "to the first day of that source item's month."
            ),
            (
                "Extract only net-new facts introduced or changed by the current source "
                "event. If the event repeats earlier context plus one new fact, draft "
                "only the new fact or facts."
            ),
            (
                "Do not treat acknowledgements such as helpful, noted, thanks, or "
                "confirmed as new facts unless they change status, timeline, commitment, "
                "priority, risk, dependency, owner, or next action."
            ),
            (
                "Do not extract facts from acknowledgement clauses such as 'the X "
                "estimate is helpful' or 'noted on X'; those clauses are references to "
                "earlier information, not net-new source facts."
            ),
            (
                "Do not join update clauses with semicolons. If a semicolon would be "
                "needed, split the content into separate bullet points instead."
            ),
        ],
    }


def source_event_extraction_system_prompt() -> str:
    return (
        "You are the source-event extraction agent for Cloud AI Software Ecosystem Updates. "
        "Follow the developer-owned rulebook exactly. Return one JSON object only. "
        "The JSON must satisfy the provided output contract before any downstream "
        "system can use it."
    )


def parse_model_json(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ModelAdapterOutputError("Model returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ModelAdapterOutputError("Model extraction response must be a JSON object.")
    return parsed
