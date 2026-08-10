# Feature 12 - Contributor Connected Sources

## Goal

Add contributor-owned, partner-specific Connected Source requests to Cloud AI
Software Ecosystem Updates.

Connected Sources are separate from Resource Links and separate from uploaded
Partner Files. They answer:

- "Which partner-specific sources should the system actively use to generate
  Pending Updates after Admin approval and system testing?"

This feature creates the contributor request and management surface. Global
integration credentials are still owned by Feature 13. Admin approval and
activation are still owned by Feature 14.

## Product Decisions

- Contributors can submit partner-specific source requests.
- Contributors can only manage sources for assigned active partners.
- New requests start as `pending`.
- Contributor UI does not show global secrets.
- Contributor UI does not show raw source excerpts.
- Contributor UI does not mention polling.
- Contributor-visible status maps internal technical statuses to simpler labels.
- Exact duplicates for the same partner/type/identifier are rejected.
- Archived sources remain in the database but are hidden from the active
  contributor table and excluded from dashboard counts.
- Partner Files remain visible as a separate lower section in the Connected
  Sources screen.

## Database Scope

Added migration:

- `0007_connected_sources`

Added tables:

- `connected_sources`
- `connected_source_jira_issues`
- `connected_source_slack_channels`
- `connected_source_sharepoint_files`
- `connected_source_confluence_pages`
- `connected_source_github_targets`

### `connected_sources`

Key columns:

- `connected_source_id`
  - Primary key.
- `partner_id`
  - Foreign key to `partners.partner_id`.
- `source_type`
  - Jira issue, Slack channel, SharePoint file, Confluence page, GitHub repo,
    GitHub issue, or GitHub pull request.
- `status`
  - `pending`, `needs_access_setup`, `active`, `rejected`, `disabled`,
    `archived`, or `failed`.
- `display_name`
  - Contributor-entered or system-derived name.
- `source_url`
  - URL for URL-based sources.
- `external_identifier`
  - Normalized identifier used for exact duplicate checks.
- `created_by`
  - Contributor who requested the source.
- `approved_by`, `approved_at`
  - Reserved for Admin approval.
- `rejected_at`
  - Reserved for Admin rejection.
- `disabled_at`
  - Used when active sources are paused.
- `archived_at`
  - Used when a contributor archives a source.
- `last_tested_at`, `last_error_summary`
  - Reserved for Admin/system source tests.

## Backend Scope

Added model:

- `apps/api/app/db/models/connected_source.py`

Added Contributor Connected Sources domain:

- `apps/api/app/domains/contributor/connected_sources/schemas.py`
- `apps/api/app/domains/contributor/connected_sources/service.py`
- `apps/api/app/domains/contributor/connected_sources/router.py`

Updated:

- `apps/api/app/main.py`
- `apps/api/app/db/models/__init__.py`
- `apps/api/app/domains/contributor/partners/service.py`

Backend behavior:

- Jira source must be a single issue URL containing an issue key.
- Slack source requires:
  - channel name
  - channel ID
  - bot/app invited confirmation
- SharePoint source requires a file URL.
- Confluence source requires a page URL.
- GitHub source supports:
  - repository URL
  - issue URL
  - pull request URL
- GitHub URL kind must match the selected source type.
- Exact duplicate requests are rejected with `409`.
- Contributor can edit/resubmit only pending or rejected sources.
- Contributor can archive a source.
- Contributor can pause active sources.
- Contributor can resume paused sources.

## API Scope

Added:

- `GET /api/contributor/partners/{partner_id}/connected-sources`
  - Lists connected sources for the assigned partner.

- `POST /api/contributor/partners/{partner_id}/connected-sources`
  - Creates a pending source request.

- `PATCH /api/contributor/partners/{partner_id}/connected-sources/{connected_source_id}`
  - Edits/resubmits a pending or rejected source.

- `POST /api/contributor/partners/{partner_id}/connected-sources/{connected_source_id}/archive`
  - Archives a source.

- `POST /api/contributor/partners/{partner_id}/connected-sources/{connected_source_id}/pause`
  - Pauses an active source.

- `POST /api/contributor/partners/{partner_id}/connected-sources/{connected_source_id}/resume`
  - Resumes a paused source.

## Client Scope

Added:

- `apps/web/src/features/contributor/contributor-connected-sources-api.ts`
- `apps/web/src/features/contributor/ContributorConnectedSourcesPanel.tsx`

Updated:

- `apps/web/src/features/contributor/ContributorDashboardShell.tsx`
- `apps/web/src/features/contributor/ContributorUploadsPanel.tsx`
- `apps/web/src/app/globals.css`

Client behavior:

- Connected Sources tab now contains:
  - source request form
  - connected source status table
  - Partner Files section
- Contributors can request:
  - Jira Issue
  - Slack Channel
  - SharePoint File
  - Confluence Page
  - GitHub Repository
  - GitHub Issue
  - GitHub Pull Request
- Pending/rejected rows can be edited/resubmitted.
- Active rows can be paused.
- Paused rows can be resumed.
- Rows can be archived.
- Dashboard Connected Sources count refreshes after source changes.

## Acceptance Criteria

- Contributor can request each source type.
- Requests appear with Pending status.
- Exact duplicate source requests are rejected.
- Contributor sees existing connected sources.
- Contributor cannot create sources for unassigned partners.
- Connected Sources does not overlap with Resource Links.
- Global credentials are not exposed.
- Raw source excerpts are not exposed.

## Verification Notes

Verified:

- Alembic upgraded to `0007_connected_sources`.
- Backend tests passed: 15 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- Docker Compose API and web images rebuilt successfully.
- Docker Compose API service reports healthy.
- API smoke test:
  - created temporary partner assigned to Bhumik Patel
  - created Jira, Slack, SharePoint, Confluence, and GitHub PR sources
  - verified all were pending
  - verified Jira issue-key extraction
  - verified GitHub target-kind parsing
  - verified exact duplicate rejection
  - archived one source
  - verified dashboard count excluded archived source
  - cleaned temporary records
- Browser UI smoke test:
  - logged in as Bhumik Patel
  - selected temporary assigned partner
  - opened Connected Sources tab
  - submitted Jira source request
  - verified Pending row and tab count
  - submitted exact duplicate request
  - verified duplicate error message
  - cleaned temporary records

Known local note:

- Admin approval, global integration availability, source access testing, and
  activation are intentionally deferred to Features 13 and 14.
