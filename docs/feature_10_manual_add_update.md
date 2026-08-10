# Feature 10 - Manual Add Update

## Goal

Allow assigned contributors to create manual pending updates inside Cloud AI
Software Ecosystem Updates.

This feature closes the gap left by Feature 09: update lifecycle already
supported pending, approved, rejected, edit, approve, and dismiss behavior, but
contributors could not yet create a manual update from the product UI.

## Product Decisions

- Manual updates are created by contributors.
- Manual updates are scoped to one partner and one reporting cycle.
- Manual updates always enter the lifecycle as `pending`.
- Manual updates have `source_type = manual`.
- Manual updates do not store a source label or source URL.
- Manual updates reuse the same edit, approve, and dismiss behavior as
  source-generated updates.
- The current UI pattern is preserved:
  - `+ Add update`
  - inline manual update form
  - title field
  - summary field
  - cancel action
  - add-to-pending action

## Database Scope

No new migration was required.

Feature 10 uses the `partner_updates` table created in Feature 09.

Relevant columns:

- `update_id`
  - Primary key for the update.
- `partner_id`
  - Foreign key to the selected partner.
- `cycle_month`
  - First day of the selected reporting month.
- `title`
  - Contributor-entered update headline.
- `summary`
  - Contributor-entered update body.
- `source_type`
  - Set to `manual`.
- `source_label`
  - Set to `null` for manual updates.
- `source_url`
  - Set to `null` for manual updates.
- `status`
  - Created as `pending`.
- `created_by`
  - User id of the contributor who created the update.

## Backend Scope

Updated Contributor Updates domain:

- `apps/api/app/domains/contributor/updates/schemas.py`
- `apps/api/app/domains/contributor/updates/service.py`
- `apps/api/app/domains/contributor/updates/router.py`

Added request schema:

- `ManualUpdateCreateRequest`

Added service behavior:

- `create_manual_update`
  - Validates partner assignment through the existing contributor access path.
  - Creates a pending update for the requested cycle.
  - Forces manual source semantics instead of trusting client-provided source
    fields.

## API Scope

Added:

- `POST /api/contributor/partners/{partner_id}/updates?cycle=YYYY-MM`
  - Requires Contributor role.
  - Requires the partner to be assigned to the current contributor.
  - Request body:
    - `title`
    - `summary`
  - Response:
    - created `PartnerUpdateResponse`
    - `status = pending`
    - `source_type = manual`
    - `source_label = null`
    - `source_url = null`

## Client Scope

Added:

- `apps/web/src/features/contributor/ManualUpdateForm.tsx`

Updated:

- `apps/web/src/features/contributor/contributor-updates-api.ts`
- `apps/web/src/features/contributor/ContributorDashboardShell.tsx`
- `apps/web/src/features/contributor/ContributorUpdatesPanel.tsx`
- `apps/web/src/app/globals.css`

Client behavior:

- `+ Add update` opens an inline form in the partner workspace.
- Cancel closes the form without changing update state.
- Add to Pending posts the manual update to the API.
- On success:
  - the form closes
  - the active tab switches to Pending Updates
  - Pending Updates reloads
  - dashboard counts refresh
- The pending row can then be edited, approved, or dismissed using Feature 09
  lifecycle actions.

## Acceptance Criteria

- Contributor can open the manual update form.
- Contributor can cancel the manual update form.
- Contributor can create a manual update with title and summary.
- Created manual update appears in Pending Updates.
- Created manual update has no source URL or source label.
- Created manual update increments Pending Updates count.
- Manual update can be approved.
- Approved manual update appears read-only in Approved Updates.
- Contributor cannot create updates for unassigned partners.

## Verification Notes

Verified:

- Backend tests passed: 12 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- Docker Compose API and web images rebuilt successfully.
- Docker Compose API and web services started successfully.
- API smoke test:
  - logged in as Admin
  - created a temporary partner assigned to Bhumik Patel
  - logged in as Bhumik Patel
  - created a manual update for August 2026
  - verified it appeared as pending
  - verified `source_type = manual`
  - verified `source_label = null`
  - verified `source_url = null`
  - approved the update
  - verified it appeared as approved
  - deleted the temporary partner afterward
- Browser UI smoke test:
  - logged in as Bhumik Patel
  - selected a temporary assigned partner
  - opened `+ Add update`
  - entered title and summary
  - submitted with Add to Pending
  - verified Pending Updates count changed to `1`
  - verified the manual row appeared in Pending Updates
  - approved the update through the UI
  - verified Pending Updates count changed to `0`
  - verified Approved Updates count changed to `1`
  - verified the approved manual update showed as read-only
  - deleted the temporary partner afterward

Known local note:

- The Feature 10 UI is functional and consistent with the current fresh shell,
  but the full pixel match to the legacy prototype is still a later visual
  polish pass.
