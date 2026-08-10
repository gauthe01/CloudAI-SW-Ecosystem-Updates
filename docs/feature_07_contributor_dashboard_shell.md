# Feature 07 - Contributor Dashboard Shell

## Goal

Create the shared Contributor View workspace shell for Cloud AI Software
Ecosystem Updates.

This feature establishes the dashboard container that later hosts partner
metadata, pending updates, approved updates, and connected sources. It does not
create the metadata, update lifecycle, or connected source persistence tables.

## Product Decisions

- Contributor View is partner-scoped.
- Contributors can only open dashboard context for assigned active partners.
- Pending Updates is the default contributor tab.
- Final contributor tabs are:
  - Partner Metadata
  - Pending Updates
  - Approved Updates
  - Connected Sources
- The dashboard shell includes:
  - selected partner header
  - last activity
  - search input
  - reporting month selector
  - `+ Add update` action placeholder
  - tab counts
- `+ Add update` is visible but disabled until Feature 10.
- Tab content is intentionally placeholder content until Features 08-12 add
  the underlying data models and actions.

## Backend Scope

Expanded Contributor Partners domain:

- `apps/api/app/domains/contributor/partners/schemas.py`
- `apps/api/app/domains/contributor/partners/service.py`
- `apps/api/app/domains/contributor/partners/router.py`

Added dashboard context loading:

- assignment-protected partner access
- active reporting cycle
- default tab
- tab counts
- last activity placeholder

## API Scope

Added:

- `GET /api/contributor/partners/{partner_id}/dashboard-context`
  - Contributor-only.
  - Returns 403 if the partner is not assigned to the contributor.
  - Returns the active partner dashboard context.

Current response shape:

```json
{
  "partner": {
    "partner_id": "uuid",
    "name": "AWS",
    "description": "AWS partner workspace",
    "updates_count": 0,
    "connected_sources_count": 0,
    "last_activity_at": null
  },
  "active_cycle": "2026-08",
  "active_cycle_label": "August 2026",
  "default_tab": "pending_updates",
  "tab_counts": {
    "pending_updates": 0,
    "approved_updates": 0,
    "connected_sources": 0
  }
}
```

## Client Scope

Added:

- `apps/web/src/features/contributor/ContributorDashboardShell.tsx`

Updated:

- `apps/web/src/features/contributor/ContributorPartnerSelectionPanel.tsx`
- `apps/web/src/features/contributor/contributor-partners-api.ts`
- `apps/web/src/features/shell/AccountViewShell.tsx`
- `apps/web/src/app/globals.css`

Client behavior:

- The contributor partner selector now flows into the contributor dashboard
  shell.
- Single-partner contributors open directly into the dashboard shell.
- Multi-partner contributors can select a partner and then switch back.
- Contributor tabs are handled inside the dashboard shell, not the outer
  account shell.
- Active contributor tab is URL-backed with `contributor_tab`.
- Reloading `/` with `?contributor_tab=approved_updates` opens the Approved
  Updates tab.

## Acceptance Criteria

- Contributor dashboard loads only for assigned active partners.
- Unassigned partner dashboard access returns 403.
- Single-partner contributor opens directly into the partner dashboard.
- Pending Updates is the default tab.
- Contributor tabs switch correctly.
- Contributor tab state can be represented in the URL.
- Shell controls are present for search, month, and add update.

## Verification Notes

Verified:

- Backend tests passed: 10 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- Docker Compose API and web images rebuilt successfully.
- Docker Compose API service reports healthy.
- Docker Compose web service is running.
- `GET /api/contributor/partners/{partner_id}/dashboard-context` returns AWS
  context for Bhumik Patel.
- Temporary unassigned partner smoke test returned 403 and was cleaned from
  the local database.
- Browser UI confirms Bhumik opens into AWS Contributor Dashboard.
- Pending Updates loads as the default tab.
- Partner Metadata, Approved Updates, and Connected Sources tabs switch
  correctly.
- Browser deep-link to `?contributor_tab=approved_updates` opens Approved
  Updates.
- Browser console logs were clean during the UI smoke test.

Known local note:

- All tab counts are zero until the later update and connected source features
  add their tables.
- The visual treatment is still functional scaffolding. It will be aligned
  screen-by-screen with the approved legacy UI during the relevant UI-focused
  features.
