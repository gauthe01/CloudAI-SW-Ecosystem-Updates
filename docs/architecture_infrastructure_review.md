# Architecture And Infrastructure Review

Review date: 2026-08-06

## Executive Summary

The project is a containerizable FastAPI application with a clear product idea:
capture partner updates from humans and integrations, stage them for review,
store approved intelligence, and generate presenter/email/deck outputs.

The codebase is ready for a guarded single-instance AWS pilot, but it is not yet
ready for broad multi-user production. The main blockers are SQLite, local file
storage, in-process scheduler ownership, and very large mixed-responsibility
modules. The current shape is understandable, but it is not yet clean enough for
a DevOps owner to operate confidently without tribal knowledge.

## Current Runtime Components

| Area | Current implementation | Production interpretation |
| --- | --- | --- |
| Web app | FastAPI app in `dashboard/main.py`, run by Uvicorn. | Containerizable as a web service. Split routes by domain before the app grows further. |
| UI | Jinja templates and static assets under `dashboard/templates` and `dashboard/static`. | Works for server-rendered internal app. Keep static files in image or move behind CDN later. |
| Auth | Local email/password auth with signed sessions; Azure SSO mode is planned/config-driven. | Acceptable only for a controlled pilot. Production needs SSO or stronger local auth controls. |
| Database | SQLite through `sqlite3` and `aiosqlite`, with schema creation in `db/init_db.py` and additive schema guards in `core/database.py`. | Biggest production blocker. Move to PostgreSQL/RDS and explicit migrations. |
| Storage | Generated docs in `outputs/docs`; attachments in `var/uploads`. `core/attachment_storage.py` has a local adapter boundary. | Implement S3-backed storage before broad use. Avoid relying on container disk. |
| Agents/connectors | Slack, Jira, Google Drive, Microsoft 365 files, shared mailbox, GitHub, direct uploads, doc parsing, PPT/email generation. | Good product decomposition by source, but runtime orchestration still lives heavily in the web app. |
| AI provider | Centralized `get_openai_client()` and `MODELS` in `core/config.py`. | Good deployment boundary. Keep model/provider config out of agent files. |
| Background jobs | APScheduler starts from FastAPI startup when `RUN_SCHEDULER=true`. | Must be separated from web containers. Use one worker service or managed schedules. |
| Deployment | `Dockerfile`, `scripts/start_prod.sh`, ECR push script, production env template, and AWS migration notes exist. | Good start. Add infrastructure-as-code and a real ECS task/service definition. |

## Containerization Readiness

The project can be containerized. The `Dockerfile` installs dependencies, copies
the app, creates writable runtime directories, exposes port 8000, and starts the
app through `scripts/start_prod.sh`.

What is good:

- The app listens on `0.0.0.0` and a configurable `PORT`.
- `.dockerignore` excludes local databases, generated outputs, virtualenvs,
  secrets, and backup folders.
- `scripts/aws_prod_build_push.sh` can build and push to ECR.
- `/healthz` exists and returns basic runtime status.

What is risky:

- `scripts/start_prod.sh` runs `db/init_db.py` every container start. That is
  workable for SQLite pilots, but production should use explicit migrations.
- `.env.production.template` points `DATABASE_URL` and storage paths inside
  `/app`, which is container-local unless backed by external storage or a volume.
- The container does not currently separate web and worker process types.
- Dependencies in `requirements.txt` use broad lower bounds, not locked versions.
- There is no infrastructure-as-code for ECS service, task definition, IAM,
  logs, load balancer, database, S3, SQS, or secrets.

## AWS Deployment Recommendation

Preferred target for the next serious AWS step:

1. ECS Fargate web service behind HTTPS.
2. Separate ECS worker service or EventBridge-triggered ECS tasks.
3. RDS PostgreSQL or Aurora PostgreSQL for the relational database.
4. S3 for uploads, attachments, generated docs, emails, decks, and exports.
5. SQS for webhook/event ingestion and retry isolation.
6. Secrets Manager or SSM Parameter Store for app secrets and connector tokens.
7. CloudWatch Logs and alarms for app, webhooks, workers, and auth events.

EC2 can run this project, either by running the Docker container directly or by
using ECS with EC2 capacity. However, direct EC2 hosting increases operational
ownership: instance patching, Docker daemon lifecycle, process supervision,
log rotation, deploy scripts, scaling, and recovery. For this app, ECS Fargate
is cleaner unless there is an ARM infrastructure requirement to manage EC2
instances directly.

## Production Blockers

### P0: Database

Current state:

- SQLite is the active database.
- Schema is spread across `db/init_db.py` and additive checks in
  `core/database.py`.
- There are many SQLite-specific assumptions: `PRAGMA table_info`, `?`
  placeholders, SQLite transaction behavior, `AUTOINCREMENT`, JSON stored as
  text, and embeddings stored as JSON text.

Required direction:

- Introduce PostgreSQL support through a deliberate data-access layer.
- Add Alembic migrations.
- Convert JSON text columns that are queryable to JSONB.
- Store embeddings in pgvector or a dedicated vector store.
- Add backup/restore procedures and migration validation scripts.

### P0: File And Artifact Storage

Current state:

- Generated Word/PPT/email artifacts are saved under `OUTPUTS_DIR`.
- Attachments use a storage abstraction but only local disk is implemented.
- Several upload/parse paths use temporary local files.

Required direction:

- Implement an S3 storage adapter.
- Expand storage abstraction beyond manual attachments to generated outputs and
  uploaded source documents.
- Store metadata in DB, bytes in S3.
- Use lifecycle policies for staged uploads and temporary exports.

### P0: Web/Worker Separation

Current state:

- FastAPI startup initializes schema and may start many scheduler jobs.
- Scaling web containers with `RUN_SCHEDULER=true` risks duplicate polling and
  duplicate ingestion.

Required direction:

- Run web containers with `RUN_SCHEDULER=false`.
- Move polling, webhook processing, monthly email generation, and memory refresh
  to a worker process type.
- Use SQS/EventBridge instead of SQLite-backed event queues for production
  ingestion.

### P1: Module Boundaries

Current state:

- `dashboard/main.py` is over 12,000 lines and owns routes, form handling,
  uploads, integration admin flows, AI calls, scheduler wiring, download logic,
  helper utilities, and presentation context.
- `core/database.py` is over 6,000 lines and contains both schema evolution and
  repository functions.

Required direction:

- Split `dashboard/main.py` into routers: auth, contributor, presenter,
  admin, integrations, webhooks, attachments, knowledge uploads, workstreams.
- Split database code into repositories by domain.
- Keep agents as source-specific services; keep route handlers thin.
- Add a small application service layer for workflows such as "stage update",
  "approve update", "process webhook event", and "generate report".

### P1: Security Hardening

Current state:

- Local auth can be explicitly allowed in production for a pilot.
- Password reset email support exists.
- Integration secrets are encrypted in the DB when a master key is configured.
- Config validation blocks several unsafe production settings.

Required direction:

- Prefer Azure SSO or another enterprise identity provider for production.
- Add rate limiting, CSRF protection, secure cookie settings, account lockout,
  audit logging, and admin action logging.
- Keep all runtime secrets out of `.env` files and inject them through AWS
  secrets integration.
- Define least-privilege IAM roles for web and worker tasks separately.

### P1: Observability And Operations

Current state:

- `/healthz` exists.
- There is no structured logging package, metrics, tracing, or alert definition.
- Smoke test coverage is minimal.

Required direction:

- Add structured logs with request IDs and event IDs.
- Send ECS logs to CloudWatch.
- Add alarms for 5xx rate, task restarts, queue depth, DLQ messages, failed
  integrations, failed email delivery, and DB health.
- Add `/readyz` that checks database and required runtime dependencies.

### P2: Test And Build Hygiene

Current state:

- Tests exist, including a large ingestion regression module.
- `pytest` is not installed in the current virtualenv.
- System and virtualenv Python can compile the code successfully.
- No CI workflow or lockfile is present.

Required direction:

- Add a dev/test dependency group or `requirements-dev.txt`.
- Pin or lock production dependencies.
- Add CI for lint, compile/import check, unit tests, and smoke tests.
- Add migration tests once PostgreSQL support starts.

## Recommended Target Architecture

```text
Users / External Systems
  Contributors, presenters, admins
  Slack, Jira, GitHub, Microsoft 365, Google Drive

Edge
  HTTPS domain
  Application Load Balancer or App Runner ingress

Web Service
  FastAPI container
  Server-rendered dashboard
  Auth/session handling
  Review workflows
  Webhook signature validation
  Enqueue jobs/events

Worker Service
  SQS consumers
  Scheduled pollers
  Document parsers
  AI classification
  Report/email/deck generation

Data Plane
  RDS/Aurora PostgreSQL
  S3 private buckets
  SQS queues and DLQs
  Secrets Manager / SSM Parameter Store
  KMS keys

Operations
  CloudWatch Logs
  Metrics and alarms
  Backup/restore runbooks
  Smoke tests and deployment pipeline
```

## Suggested Refactor Sequence

1. Freeze current behavior.
   - Add `requirements-dev.txt` with pytest.
   - Make collection/import checks run locally.
   - Keep a smoke test around login, health, manual update, approve, download.

2. Create process boundaries without changing the product.
   - Add `app/web.py` or keep `dashboard/main.py` as a compatibility wrapper.
   - Add `workers/main.py` with named commands: `scheduler`, `webhook-worker`,
     `monthly-report`, `poll-connectors`.
   - Use the same Docker image with different ECS commands.

3. Split routers out of `dashboard/main.py`.
   - Start with webhooks and attachments because they map directly to AWS
     storage/queue work.
   - Then split admin integrations and contributor uploads.

4. Add storage abstraction for all file outputs.
   - Promote `core/attachment_storage.py` into a generic object storage module.
   - Implement local and S3 backends.
   - Migrate download routes to object keys instead of local paths.

5. Add PostgreSQL behind an adapter.
   - Choose SQLAlchemy async or psycopg/asyncpg repository functions.
   - Add Alembic migrations.
   - Keep SQLite only for local dev if useful.

6. Replace local event queues with SQS.
   - Webhooks validate and enqueue quickly.
   - Workers process with idempotency keys.
   - Failed events move to DLQ after retries.

7. Add infrastructure-as-code.
   - ECS cluster/service/task definitions.
   - ECR repository.
   - ALB/listener/target group or App Runner service.
   - RDS, S3, SQS, Secrets Manager, IAM roles, CloudWatch log groups.

## Answer To The DevOps Questions

### Is the architecture clear?

Partially. The product architecture is clear. The infrastructure architecture is
documented in `docs/aws_production_migration.md`, but the code layout does not
yet make the architecture obvious. The largest ambiguity is that web, worker,
scheduler, integration admin, file handling, and AI orchestration are still
intermixed in `dashboard/main.py`.

### Are the components clear?

Yes at the product level:

- Web dashboard.
- Auth/session layer.
- Partner/workstream/update database.
- Source connectors and webhooks.
- Human review workflow.
- AI classification/intelligence.
- Document/email/deck generation.
- Local storage and local DB.

They should be renamed and grouped by deployable component next:

- `web`
- `worker`
- `connectors`
- `storage`
- `database`
- `agents`
- `infrastructure`

### Can it be containerized?

Yes. It already has a Dockerfile and startup script. The image can run the web
app. For production, use the same image with separate web and worker commands.

### Can it be deployed to EC2?

Yes. But direct EC2 is not the cleanest first production model. Use ECS Fargate
unless the platform team requires EC2. If EC2 is required, prefer ECS on EC2
capacity over hand-running containers on a single instance.

### Is it modular?

Partially. The agents and core helpers show modular intent. The route layer and
database layer are not modular enough yet. This is the main codebase cleanup
theme.

### Is it production-level clear?

Not yet. It is pilot-ready with guardrails. To be production-level clear, it
needs separated deployable components, cloud storage, production DB, explicit
migrations, infrastructure-as-code, observability, and security hardening.

## Immediate Next Actions

1. Do not deploy this as broad production on SQLite/local disk.
2. Decide AWS compute shape: ECS Fargate web + worker is the recommended path.
3. Create a task definition and service definition instead of relying only on
   the ECR push script.
4. Add a worker entrypoint and keep `RUN_SCHEDULER=false` for web.
5. Implement S3 object storage before enabling real uploads/generated files in
   AWS.
6. Start PostgreSQL migration planning before expanding the pilot audience.
7. Add infrastructure-as-code before asking DevOps for review.

## AWS Reference Links

- ECS/Fargate architecture:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html
- ECS launch types and capacity providers:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/capacity-launch-type-comparison.html
- ECS task execution role:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html
- ECS secrets from Secrets Manager:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html
- EventBridge Scheduler for ECS tasks:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/tasks-scheduled-eventbridge-scheduler.html
- RDS automated backups:
  https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html
- S3 server-side encryption:
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/serv-side-encryption.html
- SQS visibility timeout:
  https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
- SQS dead-letter queues:
  https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
