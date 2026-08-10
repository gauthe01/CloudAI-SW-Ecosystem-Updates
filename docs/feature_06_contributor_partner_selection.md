# Feature 06 - Contributor Partner Selection

## Goal

Let contributors enter the correct partner workspace in Cloud AI Software
Ecosystem Updates based on their admin-controlled partner assignments.

This feature turns the Feature 05 assignment model into contributor-facing
navigation. It does not implement partner metadata editing, draft updates,
approved updates, or connected sources yet.

## Product Decisions

- Contributors can be assigned to one or many partners.
- Contributors can only see active partners assigned to them.
- If a contributor has one assigned active partner, Contributor View opens
  directly into that partner workspace.
- If a contributor has multiple assigned active partners, Contributor View
  shows a partner selection screen first.
- The selection screen supports search by partner name and description.
- A selected multi-partner workspace includes a Switch partner action.
- Partner cards show placeholder metrics for:
  - Updates
  - Connected sources
  - Last activity
- Metric values are intentionally zero/null until the update and connected
  source tables are added in later features.

## Backend Scope

Expanded Contributor Partners domain:

- `apps/api/app/domains/contributor/partners/schemas.py`
- `apps/api/app/domains/contributor/partners/service.py`
- `apps/api/app/domains/contributor/partners/router.py`

Added service-level handling so contributor partner behavior can be tested
without relying on HTTP test client lifecycle details.

## API Scope

Updated:

- `GET /api/contributor/partners`
  - Contributor-only.
  - Returns active partners assigned to the current contributor.
  - Includes partner metrics:
    - `updates_count`
    - `connected_sources_count`
    - `last_activity_at`

Current response shape:

```json
{
  "partners": [
    {
      "partner_id": "uuid",
      "name": "AWS",
      "description": "AWS partner workspace",
      "updates_count": 0,
      "connected_sources_count": 0,
      "last_activity_at": null
    }
  ]
}
```

## Client Scope

Replaced the temporary assigned-partners panel with:

- `apps/web/src/features/contributor/ContributorPartnerSelectionPanel.tsx`

Updated:

- `apps/web/src/features/contributor/contributor-partners-api.ts`
- `apps/web/src/features/shell/AccountViewShell.tsx`
- `apps/web/src/app/globals.css`

Client behavior:

- Fetches assigned partners for the logged-in contributor.
- Shows an empty state if there are no assigned partners.
- Opens directly to the selected partner workspace when there is exactly one
  assigned partner.
- Shows searchable partner cards when there are multiple assigned partners.
- Keeps the current Contributor View tab structure:
  - Partner Metadata
  - Draft Updates
  - Approved Updates
  - Connected Sources

## Acceptance Criteria

- Bhumik Patel sees AWS as his assigned partner.
- Bhumik opens directly into AWS when AWS is his only active assigned partner.
- A contributor with multiple assigned partners sees a selection screen.
- Partner search filters the cards immediately.
- Selecting a card opens the selected partner workspace.
- Contributor partner API excludes archived partners.
- No admin-only partner data is exposed to contributor users.

## Verification Notes

Verified:

- Backend tests passed: 10 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- Docker Compose API and web images rebuilt successfully.
- Docker Compose API service reports healthy.
- Docker Compose web service is running.
- API health check returns `Cloud AI Software Ecosystem Updates`.
- Bhumik login works with `bhumik.patel@arm.com`.
- Bhumik contributor partner API returns AWS with metric placeholders.
- Temporary second partner smoke test confirmed:
  - API returns multiple assigned partners.
  - Contributor View switches to Select Partner.
  - Search filters the partner cards.
  - Selecting a card opens Partner Workspace.
  - Switch partner action appears in multi-partner mode.
- Temporary second partner was removed from the local database after
  verification.
- Final Bhumik contributor partner API returns only AWS.
- Browser console logs were clean during the UI smoke test.

Known local note:

- Partner metrics are placeholders until draft updates, approved updates, and
  connected source tables exist.
- Plain `pnpm` is still not globally available on the user's terminal PATH.
  The bundled pnpm path works and was used for verification.
