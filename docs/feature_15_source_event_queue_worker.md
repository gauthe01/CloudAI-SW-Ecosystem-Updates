# Feature 15 - Source Event Queue And Worker Foundation

Feature 15 adds the source-event processing backbone for Cloud AI Software
Ecosystem Updates.

## Scope

- `source_events` table for normalized source events from approved connected
  sources.
- `source_payloads` table for allowed raw/structured payload storage.
- `agent_runs` table for extraction and processing traceability.
- Source event idempotency key to prevent duplicate provider events from
  creating duplicate queue records.
- Retry and dead-letter lifecycle:
  - `pending`
  - `processing`
  - `succeeded`
  - `retrying`
  - `dead_letter`
- Worker entrypoint processes one ready source event per tick.
- Default worker handler records a successful no-op extraction until
  source-specific handlers are added in later features.

## Important Behavior

- Only active connected sources can enqueue events.
- Duplicate source events return the existing row and do not create another
  payload row.
- Slack payload handling stores technical metadata only and strips raw message
  payload/text at this foundation layer.
- Processing failures are logged in `agent_runs`, increment attempt count, and
  move the event to retrying or dead-letter depending on `max_attempts`.

## Not In Scope

- Slack signature verification and Slack event parsing.
- Jira webhook/MCP processing.
- SharePoint, Confluence, and GitHub live ingestion.
- AI extraction into Pending Updates.
- SQS integration. The local worker is DB-backed for now; AWS SQS/DLQ can wrap
  this same source event model later.
