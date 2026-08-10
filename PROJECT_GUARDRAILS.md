# Project Guardrails

## Product Name

Use this display name everywhere:

- `Cloud AI Software Ecosystem Updates`

Use this technical slug for repository, container, queue, log, and bucket names
where length permits:

- `cloud-ai-software-ecosystem-updates`

## Reference Folder Policy

`Gold/` and `gold/` are reference-only folders.

Allowed:

- Read screenshots or old UI behavior for product/design reference.
- Compare old implementation ideas during planning.

Not allowed:

- Build inside `Gold/`.
- Import code from `Gold/`.
- Copy source files from `Gold/`.
- Add runtime paths pointing into `Gold/`.
- Make tests depend on `Gold/`.
- Make Docker build contexts include `Gold/`.

The fresh build is valid only if the app runs after `Gold/` is deleted.

## Implementation Order

Follow `docs/sequential_feature_build_plan.md`.

Feature 0 is this repository foundation and guardrail setup. Feature 01 starts
the actual Next.js/FastAPI/PostgreSQL foundation.

## Architecture Rules

- Client code belongs in `apps/web`.
- API and worker code belong in `apps/api`.
- Durable relational state belongs in PostgreSQL.
- Durable files/artifacts belong in S3-compatible storage.
- Async processing belongs in a queue/worker path.
- Global integration secrets must not live in frontend code.
- Contributor-specific source mappings belong in the database.
- No polling fallback should be added when a webhook integration is available
  and working.
