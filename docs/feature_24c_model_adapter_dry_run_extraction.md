# Feature 24C - Model Adapter And Dry-Run Extraction

## Purpose

Feature 24C connects the source-event extraction infrastructure to the enterprise
OpenAI-compatible runtime without allowing model output to create contributor
updates yet.

This is intentionally a dry-run feature. The application can call the model,
validate the response contract, and record the decision in the agent run audit
trail, but `partner_updates` remain untouched until the production rulebooks are
approved through Feature 23B/23C.

## What Changed

- Added `OpenAISourceEventModelAdapter` for source-event extraction calls.
- Added a structured source-event model request builder.
- Added strict model JSON parsing before validation.
- Added `AI_SOURCE_EVENT_EXTRACTION_MODE`.
- Added `AI_SOURCE_EVENT_MAX_OUTPUT_TOKENS`.
- Added dry-run orchestration mode that validates model output and records an
  audit preview.
- Kept `infrastructure_only` as the default behavior.

## Runtime Modes

### `infrastructure_only`

Default mode.

The worker loads the rulebook, builds the extraction input envelope, records
agent run metadata, and exits without calling the model.

### `dry_run`

Opt-in mode.

The worker loads the rulebook, builds the extraction input envelope, calls the
enterprise OpenAI-compatible endpoint, validates the JSON output, and records the
validated decision in `agent_runs.output_json`.

No pending update is created in this mode.

## Model Request Shape

The model receives:

- Application name: `Cloud AI Software Ecosystem Updates`
- Task: `source_event_extraction`
- Mode: `dry_run_validation`
- Rulebook name, trace version, status, and body
- Source event input envelope
- Output contract
- Hard constraints

Raw source payloads are not copied into the request. The request receives only
the safe payload reference envelope created by Feature 24A.

## Model Output Handling

The adapter asks the model to return one JSON object. The output must satisfy the
Feature 24B contract:

- `ignore` requires `ignore_reason`.
- `create_update` requires `draft_update`.
- Unexpected fields are rejected.
- Confidence, source URL, title, summary, importance, and human-attention flags
  are validated before anything downstream can use them.

If the model output is invalid, processing fails closed and the source event can
follow the existing retry/dead-letter behavior.

## Agent Run Audit Output

Dry-run output records:

- `extraction_mode=model_dry_run`
- Rulebook name and trace version
- Input fingerprint
- Model name
- Validation status
- Model decision
- Ignore reason, when applicable
- Draft update preview, when applicable

The preview is not a database write. It exists only to verify that the model is
returning a safe shape before Feature 24D.

## Deployment Notes

This feature stays inside the existing backend image. No new container or EC2
instance is required.

Recommended AWS shape:

- API container and worker container run from the same backend image.
- Both receive AI runtime configuration from AWS Secrets Manager or SSM.
- `AI_SOURCE_EVENT_EXTRACTION_MODE` should remain `infrastructure_only` until
  rulebooks are approved and dry-run behavior has been verified.
- The worker can be switched to `dry_run` independently in a staging environment.

## UI Scope

No UI change.

Contributor Pending Updates continue to show only persisted pending updates.
Dry-run model previews remain backend audit data.

## Files Added Or Updated

- `apps/api/app/agents/extraction/model_adapter.py`
- `apps/api/app/agents/extraction/orchestrator.py`
- `apps/api/app/agents/extraction/__init__.py`
- `apps/api/app/core/config.py`
- `.env.template`
- `.env.production.template`
- `apps/api/tests/test_extraction_model_adapter.py`

## Acceptance Criteria

- AI can remain disabled locally.
- Dry-run extraction can validate `ignore` output.
- Dry-run extraction can validate `create_update` output.
- Dry-run extraction records a draft update preview only in `agent_runs`.
- No contributor-facing pending update is created from dry-run output.
- Invalid model output fails closed.
- The feature is deployable in the existing backend API/worker image.

## Still Blocked

Feature 24C does not decide what the agent should consider business relevant.
That remains blocked on:

- Feature 23B - Rulebook Business Interview
- Feature 23C - Approved Rulebook Content

Feature 24D should not create real pending updates until those decisions are
complete.
