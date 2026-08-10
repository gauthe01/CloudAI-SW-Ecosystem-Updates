# Feature 1.1 - Account Access Requests

Product: Cloud AI Software Ecosystem Updates
Status: implemented locally

## Purpose

Provide a local pilot access path while ARM SSO is pending.

The sign-in page remains the main entry point. Users who are not yet configured
can submit an ARM-only access request with their name, ARM email ID, and chosen
local pilot password. Admins review the request from the Team section.

## Product Decisions

- Access requests can be for contributor or presenter usage, but the request
  itself does not choose roles.
- Admin approval creates an active user account with the requester-provided
  password.
- Admin must assign at least one role while approving the request.
- Request access requires an `@arm.com` email address.
- Presenter pilot access should still use a password. There is no blank-password
  presenter route.
- Passwords are never stored in plain text.

## Backend Scope

New table:

- `account_access_requests`

Lifecycle:

- `pending`: submitted by a requester.
- `approved`: reviewed by an admin and converted into a local user.
- `rejected`: reviewed by an admin and not converted.

Public API:

- `POST /api/access-requests`

Admin API:

- `GET /api/admin/access-requests`
- `POST /api/admin/access-requests/{request_id}/approve`
- `POST /api/admin/access-requests/{request_id}/reject`

Approval behavior:

- Creates a row in `users`.
- Creates a row in `user_local_credentials`.
- Creates one or more `user_role_assignments` selected by the admin at approval
  time.

## Client Scope

New screen:

- `/request-access`

Changed screens:

- `/login`
- Admin Console > Team

Login page:

- Shows a `Request access` link.

Request access page:

- Uses the same split sign-in layout.
- Captures name, ARM email ID, password, and confirm password.
- Shows password rules below the password fields before submission.
- Shows a confirmation message after submission.

Admin Team:

- Shows access requests above the Team table.
- Admin selects contributor, presenter, and/or admin roles before approving.
- Admin can approve or reject pending requests.
- Approved users appear in the Team table with their assigned roles.

## Deferred

- ARM SSO integration.
- Admin password reset UI.
- Invite-email workflow.
- Role selection during request submission.
