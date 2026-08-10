# Feature 13 - Admin Global Integrations

Feature 13 adds the admin-owned global integration registry for Cloud AI
Software Ecosystem Updates.

## Scope

- Supported global integrations: Slack, Jira, SharePoint / Microsoft Graph,
  Confluence, and GitHub.
- Admins can save or rotate global credentials.
- Saved credential values are never returned to the frontend.
- Admins can run a readiness test and enable or disable an integration.
- Contributor-specific configuration remains outside this screen:
  Slack channel IDs, Jira issue URLs, SharePoint file URLs, Confluence page
  URLs, GitHub repositories/issues/PRs, and bot invitation confirmations are
  still handled through contributor Connected Sources.

## Current Readiness Test Behavior

The current test action is a local readiness check. It verifies that every
required credential field has been configured and then marks the integration as
enabled. It does not call live Slack, Jira, Microsoft Graph, Confluence, or
GitHub APIs yet because real IT-approved credentials and webhook/network access
are not available in the local build.

## Production Hardening Path

The local secret adapter stores a non-returned managed local handle and a
fingerprint for rotation/change detection. Production deployment should replace
this with AWS Secrets Manager or KMS-backed encryption before live third-party
connector calls are implemented.
