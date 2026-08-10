# Feature 20 - GitHub Connected Source Processing

Feature 20 adds GitHub repository, issue, and pull request connected source
processing for Cloud AI Software Ecosystem Updates.

## Scope

- GitHub webhook endpoint:
  - `POST /api/webhooks/github/events`
- Admin-owned GitHub global credentials:
  - App ID
  - Private Key
  - Webhook Secret
- HMAC-style webhook signature validation using:
  - `X-Hub-Signature-256`
  - fallback `X-Hub-Signature`
- GitHub event routing using:
  - `X-GitHub-Event`
  - `X-GitHub-Delivery`
- Active connected-source mapping by GitHub target scope:
  - repository
  - issue
  - pull request
- Source event enqueueing for approved GitHub sources.
- Duplicate protection per connected source and GitHub delivery.
- Immediate local processing into Pending Updates when an event passes the
  developer-owned GitHub meaningfulness rule.
- Approved GitHub connected sources create or restore partner Resource Links
  through the shared connected-source approval behavior.

## Credential Boundary

Global GitHub configuration remains admin-owned:

- app ID
- private key
- webhook secret

Contributor-owned configuration remains source-specific:

- partner
- GitHub repository URL
- GitHub issue URL
- GitHub pull request URL

Organization-wide, user-wide, and broad GitHub search ingestion remain out of
scope for v1.

## Scope Matching

The webhook resolver is intentionally scope-aware:

- Repository sources can process repository-level events such as push events.
- Issue sources process matching issue events.
- Pull request sources process matching pull request events.
- If multiple approved sources match the same webhook delivery, each source can
  create its own source event and Pending Update.

This matches the product rule that one update belongs to one source, while
events matching multiple sources can create separate updates.

## Storage Behavior

The source event stores technical metadata only. Raw GitHub webhook payloads and
raw issue/PR/comment bodies are not persisted in `source_payloads`.

The webhook payload is used in memory for the current local extraction pass, then
only the generated Pending Update and technical source-event metadata are
retained.

## Processing Rule

The current local rulebook is deterministic and developer-owned:

- process only active GitHub connected sources
- reject invalid webhook signatures
- process repository, issue, and pull request scopes separately
- ignore unsupported events
- ignore delete/transfer-style actions
- create a Pending Update for meaningful events such as issue opened/edited,
  PR opened/synchronized/review requested, comments created, reviews submitted,
  releases published, and repository pushes

This is a placeholder extraction layer. Later agentic extraction can use a
GitHub-specific rulebook and GitHub App/API enrichment before generating updates.

## Not In Scope

- Organization-wide GitHub ingestion.
- User-wide GitHub ingestion.
- GitHub webhook registration automation.
- Live GitHub App installation-token validation.
- Live GitHub API enrichment.
- Storing raw GitHub webhook payloads.
- Admin-side rulebook editing.
