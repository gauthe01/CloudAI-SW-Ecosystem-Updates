# Feature 00 - Project Foundation

## Goal

Create a clean rebuild boundary before implementing Feature 01.

## Completed In This Step

- Created root project README.
- Added explicit project guardrails.
- Added `Gold/` and `gold/` to `.gitignore` and `.dockerignore`.
- Created clean top-level folders:
  - `apps/web`
  - `apps/api`
  - `docs`
  - `docs/runbooks`
  - `infra`
  - `scripts`
  - `tests`
- Brought planning documents into the new root from the original project docs.
- Added `.env.example` for the new product name and target stack.
- Recreated root `.env`, `.env.template`, and `.env.production.template` with
  fresh-build configuration names and placeholder-only integration secrets.

## Acceptance Criteria

- `Gold/` is not required for any new build artifact.
- The future application can run after `Gold/` is deleted.
- New code has a clear home before Feature 01 begins.
- Planning documents are available in the new root.

## Not Included

- No Next.js runtime yet.
- No FastAPI runtime yet.
- No PostgreSQL migration yet.
- No Docker Compose runtime yet.

Those begin in Feature 01.
