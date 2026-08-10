# Feature 04 - Admin Team / Users

## Goal

Allow admins to manage Team users and role assignments for Cloud AI Software
Ecosystem Updates.

This feature creates the admin-controlled user management foundation. It does
not add invitations, self-service signup, forgot password, password reset UI,
partner assignments, or SSO.

## Product Decisions

- The screen name remains `Team`.
- Admins can create users.
- Admins can edit user name, email, and roles.
- Admins can deactivate and reactivate users.
- Roles are:
  - contributor
  - presenter
  - admin
- Password values are never displayed.
- The Team UI does not include password set/reset fields.
- The Team UI does not include invitation controls.
- Local pilot credentials are controlled through environment configuration.
- An admin cannot remove their own admin role.
- An admin cannot deactivate their own account.

## Backend Scope

Created the admin users domain:

- `apps/api/app/domains/admin/users/schemas.py`
- `apps/api/app/domains/admin/users/service.py`
- `apps/api/app/domains/admin/users/router.py`

Extended identity repository behavior:

- List users.
- Get user by ID.
- Create user.
- Replace roles.
- Revoke sessions for a user.

Updated settings:

- Added `LOCAL_USER_DEFAULT_PASSWORD`.

If `LOCAL_USER_DEFAULT_PASSWORD` is configured, admin-created local users get a
local credential hash for the pilot login model. If it is not configured, users
can still be created as identity records for future SSO or later credential
activation. The password is never returned through the API or shown in the UI.

## API Scope

Added:

- `GET /api/admin/users`
  - Lists Team users.
  - Admin-only.

- `POST /api/admin/users`
  - Creates a user.
  - Assigns one or more roles.
  - Admin-only.

- `PATCH /api/admin/users/{user_id}`
  - Updates name, email, and/or roles.
  - Admin-only.

- `POST /api/admin/users/{user_id}/deactivate`
  - Deactivates a user.
  - Revokes that user's sessions.
  - Admin-only.

- `POST /api/admin/users/{user_id}/reactivate`
  - Reactivates a user.
  - Admin-only.

## Client Scope

Added Team UI under Admin Console:

- Admin Console > Team renders the Team management panel.
- Team summary counts.
- Add member form.
- Edit member form.
- Team table.
- Role checkboxes.
- Role pills.
- Active/deactivated status pill.
- Deactivate/reactivate actions.

Intentionally excluded from UI:

- Password fields.
- Password reset.
- Invitation emails.
- Self-signup.

## Acceptance Criteria

- Admin can create users.
- Admin can edit user role assignments.
- Updated roles are reflected by the auth/view model.
- Admin can deactivate/reactivate users.
- Deactivated users cannot continue using active sessions.
- Password setup is not exposed in UI.
- Non-admin users cannot access admin user APIs.

## Verification Notes

Verified:

- Backend tests passed: 8 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- API Docker image rebuilt successfully.
- Web Docker image rebuilt successfully.
- Docker Compose API service reports healthy.
- Docker Compose web service is running.
- Live admin login succeeded.
- `GET /api/admin/users` returned Team users.
- `POST /api/admin/users` created a temporary smoke-test user.
- `PATCH /api/admin/users/{user_id}` updated that user's name and roles.
- `POST /api/admin/users/{user_id}/deactivate` deactivated that user.
- `POST /api/admin/users/{user_id}/reactivate` reactivated that user.
- Temporary smoke-test user was cleaned from the database after verification.
- `/` returns HTTP 200 from the web container.

Known local note:

- Plain `pnpm` is still not globally available on the user's terminal PATH.
  The bundled pnpm path works and was used for verification.
