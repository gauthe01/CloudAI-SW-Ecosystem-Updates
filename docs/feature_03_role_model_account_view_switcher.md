# Feature 03 - Role Model and Account View Switcher

## Goal

Support Contributor, Presenter, and Admin roles in Cloud AI Software Ecosystem
Updates, including users who hold multiple roles at the same time.

This feature introduces role-aware session behavior and the first authenticated
workspace shell. It does not implement partner records, partner assignments,
metadata, updates, or admin user management yet.

## Product Decisions

- A user can hold one or more roles:
  - contributor
  - presenter
  - admin
- The active workspace view is stored on the session, not on the user record.
- Switching views affects the current browser session only.
- The default active view uses this priority:
  - admin
  - contributor
  - presenter
- Available views are still returned in the stable display order:
  contributor, presenter, admin.
- The account menu shows only views the current user can access.
- The active view is shown as active and cannot be selected again.
- Admin Console is exposed only when the user has the admin role.

## Backend Scope

Updated identity session model:

- Added `user_sessions.active_view`.
- Added Alembic migration `0002_session_active_view`.

Updated auth service behavior:

- Login resolves the default active view.
- `/api/auth/me` returns:
  - current user
  - available views
  - active view
- Active view switching validates the requested view against the user's assigned
  roles.
- If a user's role list changes later and the stored active view is no longer
  allowed, the service falls back using the same default active-view priority.

Added reusable authorization foundation:

- Current auth context dependency.
- Current user dependency.
- Role requirement dependency for future protected routes.

## API Scope

Updated:

- `POST /api/auth/login`
  - Returns `available_views` and `active_view`.

- `GET /api/auth/me`
  - Returns `available_views` and `active_view`.

Added:

- `PATCH /api/auth/active-view`
  - Accepts `active_view`.
  - Returns the updated auth context.
  - Rejects views the user does not have access to.

## Client Scope

Created an authenticated shell in `apps/web`:

- Top-right account menu.
- Display name and email in the menu trigger.
- View switcher inside the account menu.
- Contributor View option.
- Presenter View option.
- Admin Console option.
- Sign out action.
- Active-view workspace tabs.
- Authenticated `/` route.
- Unauthenticated users are redirected to `/login`.

The shell is intentionally light. It creates the role-aware container that later
features will fill with partner selection, partner metadata, contributor
updates, connected sources, presenter intelligence, and admin management.

## Acceptance Criteria

- Contributor-only users only see Contributor View.
- Presenter-only users only see Presenter View.
- Contributor and Presenter users can switch both ways.
- Admin Console is only visible to users with admin access.
- Active view is session-scoped.
- Backend rejects switching into unassigned views.
- Existing login flow continues to work.
- Web app builds successfully.

## Verification Notes

Verified:

- Alembic upgraded to `0002_session_active_view`.
- Backend tests passed: 5 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- API Docker image rebuilt successfully.
- Web Docker image rebuilt successfully.
- Docker Compose API service reports healthy.
- Docker Compose web service is running.
- API readiness returns `database: ok`.
- `POST /api/auth/login` returns:
  - roles: contributor, presenter, admin
  - available views: contributor, presenter, admin
  - active view: contributor
- `GET /api/auth/me` returns the current active view.
- `PATCH /api/auth/active-view` switches to Presenter View.
- `PATCH /api/auth/active-view` switches to Admin Console.
- `/` returns HTTP 200 from the web container.

Known local note:

- Plain `pnpm` is still not globally available on the user's terminal PATH.
  The bundled pnpm path works and was used for verification.
