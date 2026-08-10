# Feature 24B - Model Output Contract And Validation

## Purpose

Feature 24B defines the strict contract for model-like source-event extraction
output in Cloud AI Software Ecosystem Updates.

This feature still does not call the enterprise OpenAI-compatible endpoint and
does not create pending updates from model output in runtime. It builds the
validation layer that Feature 24C will use before any model result is allowed to
affect contributor-facing data.

## Why This Exists

Model output must fail closed. The system should not create draft partner
updates from vague, malformed, overlong, or unexpected output.

Feature 24B makes the future agent path safer by requiring every extraction
result to be one of two decisions:

- `ignore`
- `create_update`

Only a valid `create_update` decision can be converted into an internal
`PendingUpdateDraftCommand`.

## Backend Scope

Implemented:

- Added `SourceEventModelOutput`.
- Added `DraftUpdateOutput`.
- Added `ExtractionDecision`.
- Added `ExtractionImportance`.
- Added `ExtractionOutputValidationError`.
- Added `PendingUpdateDraftCommand`.
- Added `validate_source_event_model_output`.
- Added `pending_update_command_from_model_output`.
- Added source-event type to partner-update source-type conversion.

## Output Contract

### Ignore Decision

An ignored source event must return:

```json
{
  "decision": "ignore",
  "ignore_reason": "Formatting-only change with no business impact."
}
```

Rules:

- `ignore_reason` is required.
- `draft_update` must not be present.
- Unknown fields are rejected.

### Create Update Decision

A source event that should become a draft update must return:

```json
{
  "decision": "create_update",
  "draft_update": {
    "title": "AWS validation moved to partner review",
    "summary": "The Jira ticket now shows validation ready for review.",
    "source_label": "AWS-123",
    "source_url": "https://jira.example.com/browse/AWS-123",
    "reasoning_category": "status_change",
    "confidence": 0.82,
    "needs_human_attention": true,
    "event_importance": "high",
    "dedupe_key_hint": "AWS-123:status-review"
  }
}
```

Rules:

- `draft_update` is required.
- `title` is required, trimmed, and capped at 300 characters.
- `summary` is required, trimmed, and capped at 12,000 characters.
- `source_label` is optional and capped at 240 characters.
- `source_url` is optional but must be a valid HTTP URL when provided.
- `confidence` is required and must be between 0 and 1.
- `event_importance` must be `low`, `medium`, or `high`.
- Unknown fields are rejected.

## Internal Pending Update Command

Valid `create_update` output converts to `PendingUpdateDraftCommand`.

The command carries:

- partner ID
- source-event month
- title
- summary
- source type
- source label
- source URL
- source event key
- connected source ID
- source event ID
- reasoning category
- confidence
- human-attention flag
- event importance
- dedupe hint

This command is not written to the database in Feature 24B. It is the safe input
shape for Feature 24C.

## Source Type Mapping

Supported source-event to update-source mapping:

- `jira_issue` -> `jira`
- `slack_channel` -> `slack`
- `sharepoint_file` -> `sharepoint`
- `confluence_page` -> `confluence`
- `github_repository` -> `github`
- `github_issue` -> `github`
- `github_pull_request` -> `github`

Unsupported source types are rejected.

## Safety Behavior

The validation layer rejects:

- unknown top-level fields
- unknown draft-update fields
- blank required title or summary
- create decisions without draft content
- ignore decisions without an ignore reason
- ignore decisions that also include draft content
- confidence scores outside `0..1`
- unsupported source types
- invalid source URLs supplied by the model

## UI Requirements

No UI changes in Feature 24B.

The fields `confidence`, `needs_human_attention`, `reasoning_category`, and
`event_importance` may later become contributor-visible only if Feature 23B
decides that the Pending Updates UI should show them.

## AWS / Deployment Impact

Feature 24B stays inside the existing API/worker backend image.

No new service, database table, queue, or secret is required. On AWS, this
validation layer will run inside the worker before any model output is allowed
to create contributor-reviewable data.

## Acceptance Criteria

- Valid ignore output validates and creates no pending-update command.
- Valid create output validates and converts into an internal pending-update
  command.
- Malformed or unexpected output fails closed.
- Unsupported source types cannot produce update commands.
- No real OpenAI call is made.
- No pending update is created at runtime by this feature.

## Next Feature

Recommended next technical feature:

- Feature 24C - Model Adapter And Dry-Run Extraction

Feature 24C can add a model adapter and dry-run pathway that calls the
enterprise OpenAI-compatible endpoint only when enabled, validates the response
through Feature 24B, and records an agent run without creating draft updates
until Feature 23B/23C approve production rulebook content.
