# Feature 24D - Model-Backed Source Event Extraction

## Status

Implemented locally.

Feature 24D adds the backend write path that can convert validated
model-produced source-event extraction output into contributor-reviewable
Pending Updates.

## What Changed

- Added explicit source-event extraction mode:
  - `AI_SOURCE_EVENT_EXTRACTION_MODE=model_write`
- Kept the default local mode as:
  - `AI_SOURCE_EVENT_EXTRACTION_MODE=infrastructure_only`
- Extended the extraction orchestrator so `model_write`:
  - loads the production source rulebook
  - calls the configured model adapter
  - validates model JSON with the existing output contract
  - converts valid `create_update` output into an internal pending-update command
  - honors `draft_update.cycle_month` when the model sets it from the source
    item's timestamp
  - returns no command for valid `ignore` output
- Extended the source-event queue service so a returned pending-update command:
  - is validated against the source event partner and connected source
  - is deduped by `source_event_key`
  - creates a `partner_updates` row with `status = pending`
  - records the created update ID and count in `agent_runs.output_json`

## Safety Rules

- Invalid model output still fails closed and cannot create a Pending Update.
- The orchestrator does not write to the database directly.
- Database writes happen only in the source-event queue service transaction.
- Duplicate source-event keys do not create duplicate Pending Updates.
- Source-item timestamps must drive the pending update cycle month when they are
  present in validated model output.
- Source-event extraction should keep only net-new facts from the current source
  item. If a later same-month event repeats earlier context and adds one new
  grounded fact, the created Pending Update should include only the net-new fact
  or facts.
- All model-created updates remain contributor-reviewable Pending Updates.
- No model-created update is approved automatically.

## Runtime Modes

### `infrastructure_only`

Loads rulebooks, records traceability, and creates no Pending Updates.

### `dry_run` / `model_dry_run`

Calls the model and validates output, but stores only a draft preview in the
agent-run audit output. Creates no Pending Updates.

### `model_write`

Calls the model, validates output, and creates a contributor-reviewable Pending
Update when the validated decision is `create_update`.

## Verification

Full API test suite passed:

```bash
uv run pytest
```

Result: 103 passed.

## Operational Note

This feature makes the agentic write path available, but it does not switch the
local or production environment into write mode.

Before enabling `model_write` for a long-running worker, verify:

- enterprise OpenAI-compatible endpoint access
- approved source-event rulebooks are loaded
- source events contain enough usable source text or metadata
- connected source credentials and webhook delivery work for the target source
- agent-run audit output is acceptable in dry-run mode

## Next Step

Run controlled local source-event dry runs against the production rulebooks, then
switch a local worker to `AI_SOURCE_EVENT_EXTRACTION_MODE=model_write` for a
seeded/simulated source event before enabling it in AWS.
