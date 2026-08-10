# Feature 08 - Partner Metadata And Resource Library

## Goal

Allow contributors to save monthly partner metadata and partner-level resource
links in Cloud AI Software Ecosystem Updates.

This feature implements real persistence for the Partner Metadata tab. It does
not implement pending updates, approved updates, connected sources, or presenter
read views yet.

## Product Decisions

- Metadata is saved by partner and reporting month.
- The contributor explicitly saves metadata by clicking Save Metadata.
- Multiple edits in the same month overwrite the latest monthly snapshot.
- No intermediary edit/version history is stored.
- Partner resource links are partner-level, not month-only.
- Resource links use the simplified v1 shape:
  - Title
  - URL
  - optional Description
- Resource links can later include connected-source-generated records.
- Connected-source generated resources can be disabled/archived later without
  deleting the partner-level resource history.
- Only assigned contributors can read or save partner metadata.

## Database Scope

Added migration:

- `0004_partner_metadata_resources`

Added tables:

- `partner_metadata_snapshots`
- `partner_metadata_risks`
- `partner_resource_links`

### `partner_metadata_snapshots`

Stores the latest saved metadata for one partner and one month.

Key columns:

- `metadata_id`
  - Primary key.
- `partner_id`
  - Foreign key to `partners.partner_id`.
- `cycle_month`
  - First day of the reporting month.
- `status`
  - Green, Amber, or Red.
- `why_this_partner`
- `business_priority`
- `highlights_status`
- `goals`
- `execution_timeline`
- `saved_by`
  - Foreign key to `users.user_id`.
- `saved_at`

Constraint:

- Unique `partner_id + cycle_month`.

### `partner_metadata_risks`

Stores structured rows for Key Risks & Issues.

Key columns:

- `risk_id`
  - Primary key.
- `metadata_id`
  - Foreign key to `partner_metadata_snapshots.metadata_id`.
- `sort_order`
- `description`
- `green_action`
- `severity`
- `assigned_to`
- `due_date`
- `ramification`

### `partner_resource_links`

Stores partner-level resource links.

Key columns:

- `resource_link_id`
  - Primary key.
- `partner_id`
  - Foreign key to `partners.partner_id`.
- `title`
- `url`
- `description`
- `source_kind`
  - `manual` for contributor-entered links.
  - `connected_source` for future connected-source-created links.
- `created_by`
- `archived_at`

## Backend Scope

Added model file:

- `apps/api/app/db/models/partner_metadata.py`

Added Contributor Metadata domain:

- `apps/api/app/domains/contributor/metadata/schemas.py`
- `apps/api/app/domains/contributor/metadata/service.py`
- `apps/api/app/domains/contributor/metadata/router.py`

Registered the route in:

- `apps/api/app/main.py`

## API Scope

Added:

- `GET /api/contributor/partners/{partner_id}/metadata?cycle=YYYY-MM`
  - Returns metadata snapshot and partner resource links.
  - Contributor-only.
  - Assignment-protected.

- `PUT /api/contributor/partners/{partner_id}/metadata?cycle=YYYY-MM`
  - Saves latest monthly metadata snapshot.
  - Replaces risk rows for that monthly snapshot.
  - Replaces manual partner resource links.
  - Contributor-only.
  - Assignment-protected.

## Client Scope

Added:

- `apps/web/src/features/contributor/ContributorPartnerMetadataPanel.tsx`
- `apps/web/src/features/contributor/contributor-metadata-api.ts`

Updated:

- `apps/web/src/features/contributor/ContributorDashboardShell.tsx`
- `apps/web/src/app/globals.css`

Client behavior:

- Partner Metadata tab loads metadata for the selected partner/month.
- Contributor can edit:
  - Status
  - Why This Partner
  - Business Priority
  - Highlights / Status
  - Goals
  - Execution Timeline
  - Key Risks & Issues
  - Resource Links
- Contributor can add/remove risk rows.
- Contributor can add/remove manual resource links.
- Save Metadata persists data and shows save confirmation.

## Acceptance Criteria

- Contributor can save metadata for an assigned partner/month.
- Contributor can reload latest saved metadata.
- Multiple saves in the same month update the same snapshot.
- No intermediate edit history is created.
- Risk rows are stored structurally.
- Resource links are stored at partner level.
- Unassigned partner metadata access is denied.

## Verification Notes

Verified:

- Alembic upgraded to `0004_partner_metadata_resources`.
- Backend tests passed: 11 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- Docker Compose API and web images rebuilt successfully.
- Docker Compose API service reports healthy.
- Docker Compose web service is running.
- API smoke test created a temporary partner, saved metadata, read it back,
  and cleaned the partner afterward.
- Browser UI smoke test created a temporary partner, selected it from the
  contributor picker, saved metadata, confirmed persisted form values, checked
  console logs, and cleaned the partner afterward.

Known local note:

- The metadata UI is functional scaffolding. It is not yet a pixel match to
  the legacy metadata screen.
- Connected-source generated resource links are modeled but not produced until
  later connected source features.
