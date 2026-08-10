# Feature 01 - Fresh Project Foundation

## Goal

Create the first runnable foundation for Cloud AI Software Ecosystem Updates.

This feature does not implement login, roles, partner metadata, updates, or
integrations. It establishes the technical base those features will use.

## Backend Scope

Created in `apps/api`:

- FastAPI app factory.
- Product-named API metadata.
- Typed settings from environment variables.
- CORS configuration.
- Structured logging baseline.
- `/healthz` liveness endpoint.
- `/api/health/ready` PostgreSQL readiness endpoint.
- Async SQLAlchemy engine and session factory.
- Alembic configuration.
- Worker entrypoint placeholder.
- API Dockerfile.
- Health endpoint test.

## Client Scope

Created in `apps/web`:

- Next.js App Router foundation.
- TypeScript configuration.
- Product-named browser metadata.
- Compact foundation screen.
- Client-side API health check card.
- Web Dockerfile.

## Local Runtime Scope

Created at the repo root:

- `docker-compose.yml` with:
  - Postgres
  - API
  - Worker
  - Web
- `package.json`
- `pnpm-workspace.yaml`

## Guardrail

The fresh runtime must not depend on `Gold/`.

## Acceptance Criteria

- API package imports.
- `/healthz` works.
- Web package typechecks.
- Web app builds.
- Alembic can inspect the current revision state.
- Docker Compose describes isolated services.

## Verification Notes

Verified:

- API dependencies installed in `apps/api/.venv`.
- API health test passed.
- Ruff check passed.
- Worker `--once` command ran successfully.
- `/healthz` returned the expected product identity from a local Uvicorn server.
- `docker compose config` passed.
- Docker Desktop is running and can pull images.
- `postgres:16-alpine` pulled successfully.
- Postgres runs through Docker Compose and reports healthy.
- Alembic connects to PostgreSQL.
- API Docker image builds.
- API runs through Docker Compose.
- `/api/health/ready` returns `database: ok`.
- Frontend dependencies installed with bundled pnpm from a network where npmjs
  is reachable.
- Web app typecheck passed.
- Web app production build passed.
- Web Docker image builds.
- Web runs through Docker Compose and returns HTTP 200.

Known local note:

- Plain `pnpm` is not on the user's terminal PATH. Use the bundled pnpm path or
  install pnpm globally later.
