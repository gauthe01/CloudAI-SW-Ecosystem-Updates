# Feature 23C - First Production Source Rulebooks

## Status

Implemented locally for source-event rulebooks.

Feature 23C converts the approved Feature 23B source rulebook decision pack into
production developer-owned rulebook markdown files.

## Rulebooks Updated

- `source_event.jira`
- `source_event.slack`
- `source_event.sharepoint`
- `source_event.confluence`
- `source_event.github`

Each source-event rulebook now has:

- `status: production`
- `version: production-2026-08-11`
- source-specific allowed event scope
- extraction rules
- ignore rules
- dedupe and conflict rules
- output contract
- golden examples

## Shared Production Rules Added

- Generated updates must be grounded in actual source facts.
- No invented owners, dates, blockers, partner impact, decisions, risks,
  quantities, or status claims.
- Draft updates should be bulleted.
- Update clauses must not be joined with semicolons; split semicolon-worthy
  content into separate bullets instead.
- Quantitative information must be preserved.
- Relevant source-item links must be preserved in the extracted update line they
  support.
- Source-item timestamps determine the update month. A source item from April
  creates an April update, even if it is fetched in August.
- Prior-month source items must not be repeated in a later month just because
  they were included as context in a later fetch.
- Same-month source items must also be incremental: when a later source item
  repeats earlier context and adds one new grounded fact, the draft must include
  only the net-new fact or facts.
- Acknowledgements such as "helpful", "noted", "thanks", "confirmed", or similar
  wording are not new facts unless they change status, timeline, commitment,
  priority, risk, dependency, owner, or next action.
- All generated updates enter Pending Updates first.
- Contributor row source reveal shows only `Source: Link Title` with the link
  embedded in the title.

## Runtime Impact

This feature does not enable model-created Pending Updates yet.

The source-event extraction mode remains controlled by
`AI_SOURCE_EVENT_EXTRACTION_MODE`. The current local default is still
`infrastructure_only`, so workers load production rulebooks and record
traceability, but they do not write model-created Pending Updates until Feature
24D.

## Verification

Focused backend tests passed:

```bash
uv run pytest tests/test_rulebook_loader.py tests/test_source_event_extraction.py tests/test_extraction_model_adapter.py tests/test_source_event_queue_service.py
```

Result: 22 passed.

## Next Feature

Feature 24D - Model-Backed Source Event Extraction.

Feature 24D should use these production rulebooks to create
contributor-reviewable Pending Updates from validated model output.
