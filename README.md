# Cloud AI Software Ecosystem Updates

Fresh product-shaped rebuild for Cloud AI Software Ecosystem Updates.

This repository is being built from the planning documents in `docs/`, not from
the old prototype implementation. The old prototype may exist locally in
`Gold/` for visual and product reference only.

## Feature 0 Status

Feature 0 establishes the clean project boundary:

- `Gold/` is reference-only and deletable.
- New code lives under `apps/`, `infra/`, `scripts/`, and `tests/`.
- Planning documents live under `docs/`.
- Runtime code must not import from or depend on `Gold/`.
- Local secrets stay out of source control.

## Feature 01 Status

Feature 01 adds the first runnable foundation:

- FastAPI app in `apps/api`.
- `/healthz` API endpoint.
- `/api/health/ready` database readiness endpoint.
- Async SQLAlchemy/PostgreSQL wiring.
- Alembic migration wiring.
- Worker process placeholder.
- Next.js app in `apps/web`.
- Local Docker Compose runtime with Postgres, API, worker, and web services.

## Target Shape

```text
apps/
  web/      Next.js client application
  api/      FastAPI server and worker codebase

docs/       PRD, architecture, AWS deployment, and build plan
infra/      Terraform/CDK infrastructure later
scripts/    Developer and CI utility scripts later
tests/      Cross-app tests later
```

## Source Of Truth

Start with these documents:

- `docs/product_requirements_document.md`
- `docs/solution_architecture_tech_stack.md`
- `docs/sequential_feature_build_plan.md`
- `docs/aws_deployment_runtime_architecture.md`
- `docs/ui_reuse_gap_assessment.md`
- `docs/current_project_reuse_assessment.md`

## Gold Folder Rule

`Gold/` is a local reference archive only. The application must still build,
test, and run if `Gold/` is deleted.

## Local Commands

API:

```bash
cd apps/api
python -m uvicorn app.main:app --reload --port 8000
```

Web:

```bash
pnpm --dir apps/web dev
```

Docker Compose:

```bash
docker compose up --build
```
