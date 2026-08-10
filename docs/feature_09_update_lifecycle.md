# Feature 09 - Update Lifecycle

## Goal

Implement the core Pending Updates and Approved Updates lifecycle for Cloud AI
Software Ecosystem Updates.

This feature adds the update data model, contributor review actions, real
pending/approved lists, and dashboard counts. Manual Add Update is still
reserved for Feature 10, so update creation is available as service foundation
but not exposed as a contributor create endpoint yet.

## Product Decisions

- Updates are partner-scoped and reporting-cycle-scoped.
- Updates use one unified table.
- Supported lifecycle statuses:
  - `pending`
  - `approved`
  - `rejected`
- UI Dismiss maps to backend `rejected`.
- Rejected updates are hidden from active Pending and Approved views.
- Pending updates can be edited before approval.
- Approved updates are read-only.
- No correction flow is implemented yet.
- No intermediate edit history is stored.
- Source links are shown as source chips.

## Database Scope

Added migration:

- `0005_update_lifecycle`

Added table:

- `partner_updates`

### `partner_updates`

Key columns:

- `update_id`
  - Primary key.
- `partner_id`
  - Foreign key to `partners.partner_id`.
- `cycle_month`
  - First day of the reporting month.
- `title`
- `summary`
- `source_type`
  - `manual`, `slack`, `jira`, `sharepoint`, `confluence`, `github`, or `file`.
- `source_label`
  - Human-friendly source chip label.
- `source_url`
  - Optional external source link.
- `source_event_key`
  - Future idempotency key for source-generated events.
- `status`
  - `pending`, `approved`, or `rejected`.
- `created_by`
- `approved_by`
- `approved_at`
- `rejected_by`
- `rejected_at`

Indexes:

- `partner_id`
- `cycle_month`
- `status`
- `partner_id + cycle_month + status`
- unique `source_event_key`

## Backend Scope

Added model file:

- `apps/api/app/db/models/partner_update.py`

Added Contributor Updates domain:

- `apps/api/app/domains/contributor/updates/schemas.py`
- `apps/api/app/domains/contributor/updates/service.py`
- `apps/api/app/domains/contributor/updates/router.py`

Updated dashboard/partner context:

- `apps/api/app/domains/contributor/partners/service.py`

Registered route in:

- `apps/api/app/main.py`

## API Scope

Added:

- `GET /api/contributor/partners/{partner_id}/updates?cycle=YYYY-MM&status=pending`
  - Lists pending updates for the selected partner/month.

- `GET /api/contributor/partners/{partner_id}/updates?cycle=YYYY-MM&status=approved`
  - Lists approved updates for the selected partner/month.

- `PATCH /api/contributor/partners/{partner_id}/updates/{update_id}`
  - Edits a pending update title and summary.
  - Returns 409 if the update is not pending.

- `POST /api/contributor/partners/{partner_id}/updates/{update_id}/approve`
  - Moves a pending update to approved.

- `POST /api/contributor/partners/{partner_id}/updates/{update_id}/dismiss`
  - Moves a pending update to rejected.

Assignment protection:

- All endpoints require Contributor role.
- All endpoints require the partner to be assigned to the contributor.

## Client Scope

Added:

- `apps/web/src/features/contributor/ContributorUpdatesPanel.tsx`
- `apps/web/src/features/contributor/contributor-updates-api.ts`

Updated:

- `apps/web/src/features/contributor/ContributorDashboardShell.tsx`
- `apps/web/src/app/globals.css`

Client behavior:

- Pending Updates tab loads real pending updates.
- Approved Updates tab loads real approved updates.
- Pending rows show:
  - update title and summary
  - source chip/source link
  - status
  - last updated date
  - Edit, Approve, Dismiss actions
- Approved rows show:
  - update title and summary
  - source chip/source link
  - status
  - approved date
  - read-only label
- Search is passed through to the update list endpoint.
- Approve/Dismiss actions refresh lifecycle lists and dashboard counts.

## Acceptance Criteria

- Pending list shows current partner/month pending updates.
- Contributor can edit a pending update.
- Contributor can approve a pending update.
- Contributor can dismiss a pending update.
- Approved list shows approved updates.
- Dismissed updates disappear from active Pending and Approved lists.
- Approved updates cannot be edited.
- Dashboard tab counts use real update counts.

## Verification Notes

Verified:

- Alembic upgraded to `0005_update_lifecycle`.
- Backend tests passed: 12 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- Docker Compose API and web images rebuilt successfully.
- Docker Compose API service reports healthy.
- Docker Compose web service is running.
- API smoke test created a temporary partner, seeded pending updates, listed
  pending updates, edited one, approved one, dismissed one, verified approved
  list, verified pending list emptied, and cleaned the partner afterward.
- Browser UI smoke test created a temporary partner, seeded pending updates,
  selected the partner from Contributor View, approved one update, dismissed
  the other, verified Approved Updates shows the approved update only, checked
  console logs, and cleaned the partner afterward.

Known local note:

- Manual update creation is intentionally not exposed in the UI until Feature
  10.
- The table UI is functional and lifecycle-backed, but it is not yet visually
  matched to the legacy Pending/Approved screens.
