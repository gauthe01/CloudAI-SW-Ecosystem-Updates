# Security And Multi-Machine Deployment Notes

## Repository Safety

Do not track local secrets, service account keys, SQLite databases, generated
documents, virtualenvs, or Python bytecode. They are ignored by `.gitignore`.

If one appears in `git status`, remove it from the index without deleting the
local file:

```bash
git rm --cached <path>
```

Rotate any credential that was previously committed before sharing the repo.

## Multi-Machine Runtime

For shared internal deployments, do not run every web instance as a scheduler.
Use this pattern:

- Web instances: `RUN_SCHEDULER=false`
- One worker instance: `RUN_SCHEDULER=true`
- All instances: same `APP_SECRET_KEY`, `DATABASE_URL`, and `OUTPUTS_DIR`

Set `MULTI_MACHINE=true` only when the database and output directory are
explicitly configured for shared infrastructure.

## Required Production Settings

```env
APP_ENV=production
AUTH_MODE=azure_sso
APP_SECRET_KEY=<strong-random-secret>
MULTI_MACHINE=true
RUN_SCHEDULER=false
DATABASE_URL=/absolute/shared/path/arm_automation.db
OUTPUTS_DIR=/absolute/shared/path/outputs/docs
```

For v1, the app still uses SQLite helpers. For broad multi-user production,
plan a Postgres migration before high concurrency or multiple scheduler workers.

## Connector Secrets

Admin source mappings store only non-secret identifiers such as channel IDs,
folder IDs, project keys, mailbox names, and labels. Tokens and app credentials
must live in environment variables or the deployment secret store.
