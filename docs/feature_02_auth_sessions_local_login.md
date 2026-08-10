# Feature 02 - Auth, Sessions, and Local Login

## Goal

Implement the first identity layer for Cloud AI Software Ecosystem Updates.

This feature gives the fresh app a real local login path that can later be
replaced or extended by ARM SSO without redesigning downstream roles,
permissions, or session-aware API routes.

## Product Decisions

- The app uses local email and password login for now.
- There is no public self-signup flow.
- There is no OTP flow.
- There is no forgot-password screen in the first implementation.
- Admin-managed users will become the long-term local fallback until SSO exists.
- One user can hold multiple roles:
  - contributor
  - presenter
  - admin
- The bootstrap local admin user is configured through environment variables.

## Backend Scope

Created the identity domain in `apps/api/app/domains/identity`:

- Login request and response schemas.
- Current-user response schema.
- Session response schema.
- Identity repository functions.
- Identity service logic.
- Auth route dependencies.
- Auth API router.
- Bootstrap admin command.

Created identity database models in `apps/api/app/db/models/identity.py`:

- `users`
- `user_local_credentials`
- `user_role_assignments`
- `user_sessions`

Created security helpers in `apps/api/app/core/security.py`:

- Password hashing.
- Password verification.
- Session token generation.
- Session token hashing before database storage.

Updated API runtime:

- Added auth settings to typed configuration.
- Registered `/api/auth/*` routes in the FastAPI app.
- Added Alembic migration `0001_identity_auth`.
- Added `email-validator` for strict email parsing.

## API Scope

Implemented:

- `POST /api/auth/login`
  - Accepts email, password, and keep-signed-in preference.
  - Verifies local credentials.
  - Creates a database-backed session.
  - Returns the authenticated user and role list.
  - Sets an HTTP-only session cookie.

- `GET /api/auth/me`
  - Reads the session cookie.
  - Verifies the active session.
  - Returns the current authenticated user and role list.

- `POST /api/auth/logout`
  - Revokes the current session.
  - Clears the session cookie.

## Client Scope

Created login UI in `apps/web`:

- `/login` route.
- Product-branded split login screen.
- Email field.
- Password field.
- Show/hide password action.
- Keep-signed-in checkbox.
- Sign-in submit state.
- Error handling for failed login.

The screen intentionally excludes:

- Forgot password.
- Create account.
- OTP flow.

## Database Notes

`users`

- Stores identity, display name, and account status.
- Does not store passwords directly.

`user_local_credentials`

- Stores one local password hash per user.
- Keeps password auth separate from the user profile so SSO can be added later
  without changing the main `users` table shape.

`user_role_assignments`

- Allows a user to hold any combination of contributor, presenter, and admin
  roles.

`user_sessions`

- Stores hashed session tokens, expiry, and revocation state.
- Supports server-side logout and future audit controls.

## Environment Variables

Added local bootstrap settings:

- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_ADMIN_DISPLAY_NAME`

Added session settings:

- `SESSION_SHORT_TTL_HOURS`
- `SECURE_COOKIES`

## Acceptance Criteria

- Identity migration applies cleanly.
- Bootstrap admin can be created from environment variables.
- Login succeeds with the bootstrap admin user.
- `/api/auth/me` returns the logged-in user before logout.
- Logout revokes the session.
- `/api/auth/me` returns 401 after logout.
- Backend tests pass.
- Backend lint passes.
- Frontend typecheck passes.
- Frontend production build passes.
- Web container rebuilds and serves `/login`.

## Verification Notes

Verified:

- Alembic upgraded to `0001_identity_auth`.
- Bootstrap admin command returned `bootstrap_admin_ready`.
- API Docker container rebuilt and reports healthy.
- `POST /api/auth/login` succeeds for the bootstrap admin user.
- Login response includes admin, contributor, and presenter roles.
- `GET /api/auth/me` succeeds while the session cookie is active.
- `POST /api/auth/logout` returns `status: ok`.
- `GET /api/auth/me` returns 401 after logout.
- Backend test suite passed: 4 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- Web Docker image rebuilt successfully.
- Docker Compose web service restarted successfully.
- `/login` returns HTTP 200.
- Login HTML includes Cloud AI Software Ecosystem Updates branding.
- Login HTML does not include the removed forgot-password or create-account
  links.

Known local note:

- Plain `pnpm` is still not globally available on the user's terminal PATH.
  The bundled pnpm path works and was used for verification.
