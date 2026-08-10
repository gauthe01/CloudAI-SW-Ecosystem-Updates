# Feature 05 - Admin Partners and Assignments

## Goal

Allow admins to manage partner records and contributor partner assignments for
Cloud AI Software Ecosystem Updates.

This feature creates the partner foundation used by the contributor dashboard
and later partner metadata/update flows. It does not implement full partner
selection cards, partner metadata fields, update lifecycle, or connected
sources yet.

## Product Decisions

- Partners are independent records.
- Contributor assignments are stored in a join table.
- A partner can have many contributors.
- A contributor can have many partners.
- Only active users with the Contributor role can be assigned to a partner.
- Archived partners are hidden from contributor assigned-partner results.
- Admin can archive and restore partners.
- Local test seed has:
  - Partner: AWS
  - Assigned contributor: Bhumik Patel

## Backend Scope

Created partner models:

- `partners`
- `partner_contributor_assignments`

Created migration:

- `0003_partners_assignments`

Created Admin Partners domain:

- `apps/api/app/domains/admin/partners/schemas.py`
- `apps/api/app/domains/admin/partners/service.py`
- `apps/api/app/domains/admin/partners/router.py`

Created Contributor Partners domain:

- `apps/api/app/domains/contributor/partners/schemas.py`
- `apps/api/app/domains/contributor/partners/router.py`

## API Scope

Added:

- `GET /api/admin/partners`
  - Lists partners and assigned contributors.
  - Admin-only.

- `POST /api/admin/partners`
  - Creates partner.
  - Assigns contributors.
  - Admin-only.

- `PATCH /api/admin/partners/{partner_id}`
  - Edits partner name, description, and assignments.
  - Admin-only.

- `POST /api/admin/partners/{partner_id}/archive`
  - Archives a partner.
  - Admin-only.

- `POST /api/admin/partners/{partner_id}/restore`
  - Restores a partner.
  - Admin-only.

- `GET /api/contributor/partners`
  - Returns only active partners assigned to the current contributor.
  - Contributor-only.

## Client Scope

Added Admin Console > Partners:

- Partner table.
- Add partner form.
- Edit partner form.
- Partner description.
- Assigned contributor checkboxes.
- Status pill.
- Archive/restore action.

Added Contributor View > Partner Metadata placeholder behavior:

- Shows assigned active partners for the logged-in contributor.
- This is intentionally minimal until Feature 06 and Feature 08 expand the
  contributor experience.

## Acceptance Criteria

- Admin can add partners.
- Admin can edit partner assignments.
- Admin can archive/restore partners.
- Only active contributors can be assigned.
- Contributor View respects partner assignments.
- Bhumik Patel sees AWS as an assigned partner.

## Verification Notes

Verified:

- Alembic upgraded to `0003_partners_assignments`.
- Backend tests passed: 9 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- API Docker image rebuilt successfully.
- Web Docker image rebuilt successfully.
- Docker Compose API service reports healthy.
- Docker Compose web service is running.
- Local AWS partner assigned to Bhumik Patel.
- Admin partner API lists AWS assigned to Bhumik.
- Temporary partner smoke test covered create, edit, archive, restore.
- Temporary partner was cleaned from the database after verification.
- Bhumik's assigned-partners API returns only AWS after cleanup.
- Admin Console > Partners UI shows AWS assigned to Bhumik Patel.
- Bhumik Contributor View shows AWS and does not expose Admin Console.

Known local note:

- Plain `pnpm` is still not globally available on the user's terminal PATH.
  The bundled pnpm path works and was used for verification.
