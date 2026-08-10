# Feature 14 - Admin Connected Source Approvals

Feature 14 adds the admin approval workbench for contributor-requested connected
sources in Cloud AI Software Ecosystem Updates.

## Scope

- Admin can view all contributor connected source requests.
- Admin workbench queues:
  - Needs Review
  - Attention
  - Active
  - Rejected
  - All
- Admin can:
  - test access readiness
  - approve and activate a pending source
  - reject a source
  - mark a source as needing access setup
  - disable an active source
- The contributor-facing Connected Sources tab reflects the resulting status.
- The approval response includes partner, requester, source details, required
  integration, integration availability, duplicate count, and access test
  summary.

## Integration Gate

Approval is blocked unless the required global integration is enabled:

- Slack Channel -> Slack
- Jira Issue -> Jira
- SharePoint File -> SharePoint / Microsoft Graph
- Confluence Page -> Confluence
- GitHub Repository / Issue / Pull Request -> GitHub

The current access test is a local readiness check. If the global integration is
not enabled, the source moves to `needs_access_setup`. If it is enabled, the
source records a successful readiness result and can be approved.

## Duplicate Handling

Exact duplicates are surfaced as a count in the admin response and UI. Near
duplicates remain visible for admin judgment, matching the product decision to
keep broad source review rather than hiding potentially useful requests.

## Not In Scope

- Live external API calls to Slack, Jira, Microsoft Graph, Confluence, or
  GitHub.
- Worker/event ingestion.
- Source event queue.
- Rulebook-driven extraction from approved sources.
