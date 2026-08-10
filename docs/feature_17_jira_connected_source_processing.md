# Feature 17 - Jira Connected Source Processing

Feature 17 adds Jira issue webhook processing for Cloud AI Software Ecosystem
Updates.

## Scope

- Jira webhook endpoint:
  - `POST /api/webhooks/jira/events`
- Jira webhook request verification using the admin-configured Jira Webhook
  Secret.
- Active connected-source mapping by Jira issue key.
- Source event enqueueing for approved Jira issue sources.
- Duplicate protection using Jira event identity.
- Immediate local processing into Pending Updates when the developer-owned Jira
  meaningfulness rule passes.
- Pending Updates preserve source traceability through:
  - `connected_source_id`
  - `source_event_id`
  - `source_event_key`
  - Jira issue URL

## Credential Boundary

Global Jira credentials remain admin-owned:

- Base URL
- Service Token
- Webhook Secret

Contributor-owned configuration remains source-specific:

- partner
- single Jira issue URL

Only a single Jira issue source is supported for v1 connected-source ingestion.
Project-wide, epic-wide, filter/JQL, and linked-child-ticket ingestion remain
out of scope until the rulebook and extraction contract are expanded.

## Retention Behavior

Jira raw webhook payloads are not persisted.

For Jira events, `source_payloads` stores a technical-metadata-only payload row
with:

- `raw_payload_json = null`
- `raw_text_encrypted = null`
- `retention_policy = technical_metadata_only`

`source_events.technical_metadata` stores operational fields such as Jira event
type, issue key, issue ID, project key, issue type, status, priority, changelog
ID, changed fields, and hashed user identifiers.

## Processing Rule

The current local rulebook is deterministic and developer-owned:

- ignore issue-deleted events
- create a Pending Update for issue-created and comment-created events
- create a Pending Update for issue-updated events when meaningful fields change
- include status, priority, changed fields, and issue summary in the generated
  Pending Update

This is a placeholder extraction layer. Later agentic extraction can use Jira
MCP/service access to enrich the update while keeping the same source-event and
Pending Update contract.

## Not In Scope

- Jira polling.
- Project-wide ingestion.
- Epic-wide ingestion.
- JQL/filter ingestion.
- Linked child ticket traversal.
- Storing raw Jira payloads.
- Full AI extraction and summarization.
- Live Jira API token validation beyond local readiness checks.
