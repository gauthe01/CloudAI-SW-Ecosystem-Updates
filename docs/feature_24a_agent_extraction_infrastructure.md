# Feature 24A - Agent Extraction Infrastructure

## Purpose

Feature 24A adds the structural extraction layer that future model-backed source
event processing will use in Cloud AI Software Ecosystem Updates.

This feature intentionally does not decide business rules and does not call the
enterprise OpenAI-compatible endpoint. Feature 23B and Feature 23C remain the
gates for production rulebook behavior.

## Why This Exists

The app already receives source events and can process them through deterministic
local handlers. To make the product genuinely agentic without creating code
slop, the next step is a shared extraction contract:

- Each source event resolves to one registered rulebook.
- The worker builds a sanitized input envelope.
- Raw retained payloads are referenced, not blindly copied into model input.
- The agent output can hand rulebook/model metadata back to `agent_runs`.
- Model-backed extraction can be added later without rewriting every webhook.

## Backend Scope

Implemented:

- Added `app.agents.extraction`.
- Added a source-type to rulebook resolver:
  - `slack_channel` -> `source_event.slack`
  - `jira_issue` -> `source_event.jira`
  - `sharepoint_file` -> `source_event.sharepoint`
  - `confluence_page` -> `source_event.confluence`
  - `github_repository`, `github_issue`, `github_pull_request` ->
    `source_event.github`
- Added `SourceEventExtractionInput`, a sanitized source-event input envelope.
- Added payload reference metadata:
  - whether payload exists
  - retention policy
  - whether structured payload exists
  - whether encrypted text exists
  - storage object reference
- Added deterministic input fingerprinting.
- Added `SourceEventExtractionOrchestrator`.
- Added infrastructure-only extraction result.
- Updated the source-event queue default handler to use the extraction
  infrastructure.
- Updated `agent_runs` success metadata from extraction output:
  - `rulebook_name`
  - `rulebook_version`
  - `model_name`
  - `input_fingerprint`

## Not In Scope

- No OpenAI call.
- No prompt execution.
- No real production rulebook content.
- No source event to pending-update generation through the new agent path.
- No UI changes.
- No database migration.
- No replacement of existing source-specific deterministic webhook processors.

## Current Runtime Behavior

When the worker processes a source event without a source-specific handler, it
now goes through the extraction infrastructure and returns:

- `pending_updates_created = 0`
- `extraction_mode = infrastructure_only`
- selected rulebook name
- selected rulebook trace version
- input fingerprint
- a reason explaining that model-backed extraction is gated by Feature 23B/23C

This means the plumbing can be tested safely without producing AI-generated
draft updates before the product rulebook is approved.

## AWS / Deployment Shape

Feature 24A stays inside the existing backend image:

- API and worker containers both include the extraction package.
- The worker will be the first runtime caller for source-event extraction.
- No separate agent service is required for the first AWS deployment.
- Future scaling can split agent workloads into a separate worker service if
  extraction throughput or isolation requires it.

The enterprise AI endpoint remains configured through environment/secrets
settings introduced in Feature 22.

## Acceptance Criteria

- Supported source types resolve to the correct registered rulebook.
- Unknown source types are rejected clearly.
- The extraction input envelope does not copy raw retained payloads into model
  payloads.
- Infrastructure-only extraction records the selected rulebook and trace version.
- Source-event worker default processing succeeds without creating draft
  updates.
- Existing source-specific webhook processors are not functionally changed.

## Next Feature

Recommended next technical feature:

- Feature 24B - Model Output Contract And Validation

Feature 24B should define strict JSON schemas and validation behavior for model
outputs while still avoiding real business extraction rules until Feature 23B
and Feature 23C are complete.
