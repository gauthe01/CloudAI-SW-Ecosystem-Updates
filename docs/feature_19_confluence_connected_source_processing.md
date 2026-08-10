# Feature 19 - Confluence Connected Source Processing

Feature 19 adds Confluence single-page connected source processing for Cloud AI
Software Ecosystem Updates.

## Scope

- Confluence webhook endpoint:
  - `POST /api/webhooks/confluence/events`
- Admin-owned Confluence global credentials:
  - Base URL
  - Service Token
  - Webhook Secret
- HMAC-style webhook signature validation using:
  - `X-Hub-Signature-256`
  - fallback `X-Hub-Signature`
- Active connected-source mapping by Confluence page URL.
- Source event enqueueing for approved Confluence page sources.
- Duplicate protection using Confluence event type, page identity, version, and
  event timestamp.
- Immediate local processing into Pending Updates when page content passes the
  developer-owned Confluence meaningfulness rule.
- Approved link-based connected sources now create or restore partner Resource
  Links with `source_kind = connected_source`.

## Credential Boundary

Global Confluence configuration remains admin-owned:

- base URL
- service token
- webhook secret

Contributor-owned configuration remains source-specific:

- partner
- single Confluence page URL

Space-wide, label-wide, and broad Confluence search ingestion remain out of
scope for v1.

## Storage Behavior

The source event stores technical metadata only. Raw Confluence page bodies and
raw webhook payloads are not persisted in `source_payloads`.

The webhook payload is used in memory for the current local extraction pass, then
only the generated Pending Update and technical source-event metadata are
retained.

## Processing Rule

The current local rulebook is deterministic and developer-owned:

- process only active single-page Confluence connected sources
- ignore unmapped pages
- reject invalid webhook signatures
- ignore delete and attachment events
- create a Pending Update when the sanitized page text includes a
  business-relevant keyword such as risk, blocker, decision, milestone, status,
  release, priority, issue, or update

This is a placeholder extraction layer. Later agentic extraction can use a
Confluence-specific rulebook and a REST/MCP-style connector to fetch current
page content before generating updates.

## Not In Scope

- Space-wide Confluence ingestion.
- Label/search based Confluence ingestion.
- Live Confluence webhook registration automation.
- Live REST/MCP page fetch enrichment.
- Storing raw Confluence page bodies.
- Admin-side rulebook editing.
