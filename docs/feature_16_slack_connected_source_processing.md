# Feature 16 - Slack Connected Source Processing

Feature 16 adds the first live webhook ingestion path for Cloud AI Software
Ecosystem Updates: Slack channel events from approved contributor connected
sources.

## Scope

- Slack webhook endpoint:
  - `POST /api/webhooks/slack/events`
- Slack URL verification support for Slack app setup.
- Slack request verification using:
  - `X-Slack-Request-Timestamp`
  - `X-Slack-Signature`
  - admin-configured Slack Signing Secret
- Active connected-source mapping by Slack channel ID.
- Source event enqueueing for mapped channels.
- Duplicate protection using Slack event ID.
- Immediate local processing into Pending Updates when the developer-owned
  Slack meaningfulness rule passes.
- Pending Updates preserve source traceability through:
  - `connected_source_id`
  - `source_event_id`
  - `source_event_key`
  - Slack channel redirect URL

## Credential Boundary

Global Slack credentials remain admin-owned:

- Signing Secret
- Bot Token

Contributor-owned configuration remains source-specific:

- partner
- Slack channel name
- Slack channel ID
- confirmation that the bot was invited to the channel

This keeps developer/admin credentials separate from contributor source mapping,
matching the product architecture decision.

## Retention Behavior

Slack raw message text and raw webhook payloads are not persisted.

For Slack events, `source_payloads` stores a technical-metadata-only payload row
with:

- `raw_payload_json = null`
- `raw_text_encrypted = null`
- `retention_policy = technical_metadata_only`

`source_events.technical_metadata` stores only operational fields such as Slack
event ID, channel ID, channel name, message timestamp, thread timestamp, sender
hash, and message subtype.

## Processing Rule

The current local rulebook is intentionally simple and developer-owned:

- ignore unsupported Slack event types
- ignore join/leave/delete message subtypes
- create a Pending Update if the cleaned message is long enough or includes a
  business-relevant keyword such as risk, blocker, decision, milestone, status,
  release, priority, issue, or update

This is a placeholder rulebook implementation. Later agentic extraction can
replace the heuristic while keeping the same source-event and Pending Update
contract.

## Not In Scope

- Polling Slack.
- Showing raw Slack excerpts in the UI.
- Storing raw Slack messages for replay.
- Full AI summarization/classification.
- Slack OAuth installation flow.
- Slack channel invitation automation.
- AWS SQS ingestion. The local webhook currently writes directly to the DB
  queue model.
