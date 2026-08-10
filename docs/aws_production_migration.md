# AWS Production Migration Checklist

Living document for moving Cloud AI Software Ecosystem Updates from
local development to an AWS-hosted production deployment.

## Current Local Assumptions

- FastAPI app runs with `uvicorn` from this repo.
- Local auth is enabled with email/password accounts and signed cookie sessions.
- Passwords are stored as PBKDF2-SHA256 hashes in the `users` table.
- Password reset emails use SMTP when configured; otherwise local dev writes
  reset emails into `outputs/dev_emails`.
- SQLite is the active database at `db/arm_automation.db`.
- Generated docs and local email previews are written under `outputs/`.
- Background scheduler jobs can run inside the web process when
  `RUN_SCHEDULER=true`.

## Migration Items For AWS

## Direct-To-PROD Pilot Decision

The project will skip an AWS DEV deployment for the first hosted pilot because
the laptop remains the development environment. Use the AWS production account,
`IPG-LoB-Infra-SE-PROD` (`532275579171`), but roll out in guarded production
phases:

1. Build and test the production container locally.
2. Deploy the web service to AWS PROD with webhooks disabled.
3. Run private smoke tests against the production URL.
4. Enable one connector at a time, starting with Slack.
5. Keep localhost available for day-to-day development throughout.

This does not make the first deployment broadly production-ready. Before wider
team usage, complete the database, storage, worker, backup, and monitoring
items below.

### Current Step Status

2026-07-27:

- Local production-mode startup was verified outside Docker with
  `APP_ENV=production`, `MULTI_MACHINE=true`, `RUN_SCHEDULER=false`, webhooks
  disabled, and throwaway absolute database/storage paths.
- `scripts/aws_prod_smoke_test.sh` passed against the local production-mode
  server.
- Empty production-mode databases no longer seed local dev users by default.
  `SEED_LOCAL_USERS` defaults to true only for `APP_ENV=local`; production
  templates set it to false explicitly.
- Docker image build is blocked locally until Docker Desktop is signed in with
  the required `armlimited` organization membership.
- User terminal confirmed AWS CLI access to PROD account `532275579171` through
  `AWSReservedSSO_ProjAdmins_a986dd66ef3cf266`.
- PROD ECR repository `arm-ecosystem-platform` exists in `us-east-1`; it was
  created on 2026-07-13 and contains active images pushed on 2026-07-13.
- The active tagged application image is
  `532275579171.dkr.ecr.us-east-1.amazonaws.com/arm-ecosystem-platform:86559eb`
  with digest
  `sha256:1ec6e77e2cd57dfd506c1327cf14ced81dec69be31cb8d3487c2502c595ff00c`.
  It was pushed on 2026-07-13 at 18:43:04 Pacific and last pulled on
  2026-07-22 at 07:35:27 Pacific.
- Tag `86559eb` corresponds to the `Add AWS production deployment scaffolding`
  commit. It is older than current repo `HEAD`, so any new deployment should
  rebuild and push a fresh image after local Docker access is restored.
- ECS cluster `arm-ecosystem-prod` exists in `us-east-1`.
- App Runner has no services in `us-east-1`.
- ECS cluster `arm-ecosystem-prod` currently has no services and no running
  tasks. The app image has been pushed to ECR, but the web service is not
  deployed/running yet.
- ECS has no `arm-ecosystem-platform` task definitions and no stopped tasks in
  `arm-ecosystem-prod`, so there is no prior ECS web app deployment to inspect
  or resume.
- Networking discovery found three VPCs in `us-east-1`: default
  `vpc-04e52941ed727e458`, `julsua01-vpc-apx-llvm`
  `vpc-08cbb02c37880094b`, and `bert-r8g-vpc`
  `vpc-060a199f15250ee79`. Do not choose a VPC for deployment until route
  tables, available IPs, and security groups are checked with narrower queries.
- Narrowed discovery for default VPC `vpc-04e52941ed727e458` found public
  subnets named `NPS-Inspected-pub-gwlbe-public-0-1a`,
  `NPS-Inspected-pub-gwlbe-public-0-1b`, and
  `NPS-Inspected-pub-gwlbe-public-0-1c`, but they are `/28` subnets with only
  about 9-10 available IPs. Treat these as too tight for a new ALB unless AWS
  network owners approve them.
- The same default VPC has larger private-ish benchmark subnets such as
  `benchdnn_`, `llama-pytorch_3`, `mlperf`, `llamacpp`, and others. These look
  unrelated to this web app and should not be reused without owner approval.
- The route-table/security-group query output was truncated in the shared
  paste, so deployment networking remains undecided.
- `us-east-1` currently has zero Elastic Load Balancing v2 load balancers, so
  there is no existing ALB/NLB to reuse for the first ECS service.
- Default VPC route-table discovery showed at least two route tables with
  active `0.0.0.0/0` routes to internet gateway `igw-0a0133807e8f1c1f1`, but
  the pasted output was truncated before all associations could be reviewed.
- With `AWS_PAGER` disabled, route/subnet discovery showed the default VPC main
  route table `rtb-01df2b446c66e981b` has an active internet gateway default
  route. Large public default subnets are available and have enough free IPs for
  an ALB:
  - `subnet-05bdf68ff6f9d34f9` in `us-east-1a`, `172.31.0.0/20`, 4086
    available IPs.
  - `subnet-078bbb5f71e9bf770` in `us-east-1b`, `172.31.80.0/20`, 4074
    available IPs.
  - `subnet-0b3b88a584fde4b7e` in `us-east-1c`, `172.31.16.0/20`, 4083
    available IPs.
  - `subnet-0b84df0dacff5e15d` in `us-east-1f`, `172.31.64.0/20`, 4081
    available IPs.
- For the first guarded pilot, prefer the large default public subnets over the
  tiny inspected `/28` subnets. Later production hardening should revisit
  private task subnets, NAT/egress, and network-owner approval.
- IAM discovery found the ECS service-linked role
  `AWSServiceRoleForECS`, but no `ecsTaskExecutionRole`. Before registering a
  Fargate task definition, create an ECS task execution role with the
  `AmazonECSTaskExecutionRolePolicy` managed policy.
- Creating `ecsTaskExecutionRole` was denied for the current `ProjAdmins` SSO
  role because it lacks `iam:CreateRole` and `iam:AttachRolePolicy`. This does
  not require the role name `ecsTaskExecutionRole`, but ECS/Fargate still needs
  an execution role or equivalent existing role that `ecs-tasks.amazonaws.com`
  can assume and that can pull ECR images/write CloudWatch logs.
- `list-entities-for-policy` for AWS managed policy
  `AmazonECSTaskExecutionRolePolicy` returned no attached roles, so there is no
  standard managed-policy task execution role currently discoverable in the
  account.
- Searching IAM roles for ECS/task-like names found only
  `AWSServiceRoleForECS`, which is the ECS service-linked role and not a
  Fargate task execution role. The first ECS deployment is blocked on an
  approved task execution role from IAM/platform owners.
- The Codex app shell does not inherit the user's temporary AWS access portal
  credentials, so AWS verification commands must be run from the authenticated
  terminal unless credentials are exported into the Codex shell.

### Local Tooling Needed For The PROD Push

Install these on the laptop before building and pushing the container image:

```bash
brew install --cask docker
brew install awscli
```

After installing Docker Desktop, open the Docker app once and wait until it says
Docker is running. Then confirm both tools:

```bash
docker --version
aws --version
aws sts get-caller-identity
```

The AWS identity must show account `532275579171` before running the production
image push script.

### Runtime And Hosting

- Use ECS Fargate for the direct PROD pilot because it gives control over the
  web service now and a separate worker service later.
- Build the image with `Dockerfile` and push it with
  `scripts/aws_prod_build_push.sh`.
- Run the app behind HTTPS using an AWS-managed certificate.
- Set `APP_ENV=production`.
- Set `APP_BASE_URL` to the final public domain.
- Ensure only one process owns scheduler jobs, separate from horizontally scaled
  web instances.

### Database

- Migrate from SQLite to a production database before real multi-user use.
- Recommended AWS target: Amazon RDS PostgreSQL.
- Replace SQLite-specific helper assumptions in `core/database.py` with a
  PostgreSQL-compatible data layer or migration path.
- Add schema migrations instead of relying only on `db/init_db.py`.
- Move these tables/data carefully:
  - `users`
  - `password_reset_tokens`
  - `workstreams`
  - `staged_updates`
  - `updates`
  - `pending_queue`
  - `feedback_signals`
  - `doc_cycles`
  - source connection/mapping/sync tables
  - training source/suggestion tables
- Decide whether local dev seed users should exist in production. Default: no.

### Secrets And Configuration

- Move `.env` values into AWS Secrets Manager or SSM Parameter Store.
- Never deploy local `.env`, service account JSON files, local SQLite DBs, or
  generated output directories.
- Production-required settings:

```env
APP_ENV=production
APP_SECRET_KEY=<strong-random-secret>
APP_BASE_URL=https://<production-domain>
AUTH_MODE=local
ALLOW_LOCAL_AUTH_IN_PROD=true
MULTI_MACHINE=true
RUN_SCHEDULER=false
DATABASE_URL=<production-db-url>
OUTPUTS_BACKEND=<s3-or-shared-storage>
```

- `ALLOW_LOCAL_AUTH_IN_PROD=true` is a temporary direct-PROD pilot switch. Remove
  it when `AUTH_MODE=azure_sso` becomes available.
- Until ARM SSO is live, local password auth must be limited to the pilot group
  and hardened with rate limiting, account lockout, audit logs, and email
  delivery.

### Email Delivery

- Current reset-email implementation supports SMTP.
- AWS option to evaluate later: Amazon SES.
- When SES is chosen:
  - verify sender domain/email
  - configure SPF/DKIM/DMARC
  - replace or configure SMTP settings for SES SMTP
  - set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`
  - remove reliance on `DEV_EMAIL_OUTBOX`
- Password reset email should continue using generic confirmation copy so the app
  does not reveal whether an email is registered.

### File And Document Storage

- Replace local `outputs/` storage with durable cloud storage.
- Recommended AWS target: S3 bucket for generated docs, uploaded docs, and
  temporary exports.
- Add bucket lifecycle rules for temporary/generated artifacts.
- Keep private files private by default; use signed URLs only when needed.
- Update document download routes to read from S3 or a storage abstraction.

### Sessions And Auth Hardening

- Keep `APP_SECRET_KEY` stable across all web instances so signed cookies remain
  valid.
- Add production auth scenarios before launch:
  - login rate limiting
  - account lockout after repeated failures
  - inactive/deactivated account state
  - audit logging for sign-in, sign-out, password reset, and failed attempts
  - CSRF protection for state-changing forms
  - secure cookie flags behind HTTPS
- Decide whether to keep signed-cookie sessions or move to a server-side session
  store for sign out from all devices.

### Partner Access Model

- Current manager partner selection is derived from configured `PARTNER_SLOTS`.
- Before production, decide whether managers should see all partners or only a
  scoped assignment list.
- If scoped access is required, add a user-to-partners table and migrate
  `/partners`, `/intelligence`, workstream routes, and upload routes to enforce
  that mapping consistently.
- Keep contributor single-partner redirects intact unless multi-partner
  contributor access becomes a product requirement.

### Background Jobs And Agents

- Do not run schedulers in every web container.
- Use one dedicated worker service or scheduled job owner for:
  - Slack/Jira/Drive/SharePoint polling
  - monthly exec email generation
  - workstream memory refresh
- AWS candidates:
  - ECS service for a long-running worker
  - EventBridge Scheduler plus one-off worker tasks
  - SQS if ingestion jobs need queueing/retries later

### Slack Events API Production Cutover

- The local development proof uses Slack Events API through ngrok:
  `https://<ngrok-domain>/webhooks/slack/events` forwards to
  `http://127.0.0.1:8000`.
- In AWS, remove ngrok entirely. Slack must call the production HTTPS URL:
  `https://<production-domain>/webhooks/slack/events`.
- Keep `SLACK_EVENTS_ENABLED=false` for the first production smoke test. Enable
  Slack only after `/healthz`, login, dashboard navigation, manual updates, and
  staged review pass on the production URL.
- Keep the same endpoint path, event behavior, and signature verification:
  - Slack URL verification must return the `challenge` value.
  - All real events must validate `X-Slack-Signature` and
    `X-Slack-Request-Timestamp`.
  - Invalid or stale Slack requests must be rejected before enqueueing.
- Move Slack settings from local `.env` to AWS Secrets Manager or SSM:

```env
SLACK_EVENTS_ENABLED=true
SLACK_SIGNING_SECRET=<production-slack-signing-secret>
SLACK_BOT_TOKEN=<production-bot-token>
SLACK_EVENT_WORKER_INTERVAL_SECONDS=5
```

- Do not store Slack signing secrets or bot tokens in the database,
  source mappings, checked-in files, CloudWatch logs, or deployment output.
- Replace the local SQLite-backed event queue with SQS or another production
  queue before real production use. The web container should receive, verify,
  enqueue, and return quickly; a worker should process events later.
- Run Slack event processing in a dedicated worker or exactly one scheduler
  owner. Do not run duplicate Slack workers in every scaled web container.
- Configure Slack Event Subscriptions for the production app:
  - Request URL:
    `https://<production-domain>/webhooks/slack/events`
  - Bot events:
    `message.channels` and `message.groups`
  - Bot scopes:
    `channels:history`, `channels:read`, `groups:history`, `groups:read`
- After changing Slack scopes, event subscriptions, or production URLs,
  reinstall/re-authorize the Slack app in the workspace if Slack prompts for it.
- Store Slack channel-to-partner mapping in the production database through
  Admin Source Mappings. Local `.env` channel variables such as
  `SLACK_CHANNEL_UBER` are acceptable for dev fallback only.
- In AWS, validate the cutover by sending one test message in a mapped Slack
  channel and confirming:
  - Slack receives HTTP 200 from the production endpoint.
  - The event is queued once.
  - The worker processes the event.
  - Unknown channels are retained for mapping review instead of breaking the
    pipeline.
  - Processed, duplicate, failed, and unmapped events are visible in logs/admin
    status.

### Jira Webhook Production Cutover

- The local development proof uses Jira Data Center webhooks through ngrok:
  `https://<ngrok-domain>/webhooks/jira/events` forwards to
  `http://127.0.0.1:8000`.
- In AWS, remove ngrok entirely. Jira must call the production HTTPS URL:
  `https://<production-domain>/webhooks/jira/events`.
- Keep `JIRA_EVENTS_ENABLED=false` until the Slack production cutover is stable
  and Jira admin/webhook access is confirmed.
- Configure Jira Data Center webhooks for the SPEAR/SPAR board/filter, not every
  Jira issue in the company:
  - issue created
  - issue updated
  - comment created
  - comment updated
- Move Jira settings from local `.env` to AWS Secrets Manager or SSM:

```env
JIRA_EVENTS_ENABLED=true
JIRA_WEBHOOK_SECRET=<production-jira-webhook-secret>
JIRA_EVENT_WORKER_INTERVAL_SECONDS=5
JIRA_BASE_URL=https://jira.arm.com
JIRA_BACKFILL_ENABLED=true
JIRA_POLL_INTERVAL_HOURS=24
```

- Store the Jira service account PAT/token in the production secret store, not
  in checked-in files or CloudWatch output. The webhook payload should only
  identify the issue; the worker should fetch full issue details with the
  service account.
- Replace the local SQLite-backed event queue with SQS or another production
  queue. The web container should verify the webhook, enqueue it, and return
  quickly; a worker should fetch issue details and stage updates later.
- Run Jira event processing in a dedicated worker or exactly one scheduler
  owner. Do not run duplicate Jira workers in every scaled web container.
- Keep scheduled Jira backfill enabled as a safety net for missed webhook
  deliveries, downtime, permission changes, or replay needs. Backfill is not the
  primary ingestion path.
- Store Jira `Customers` values to dashboard partner mappings in the production
  database through Admin Source Mappings. Confirm the actual Jira custom field id
  for `Customers` during production setup.
- Validate the cutover by creating or updating one mapped SPEAR/SPAR test issue
  and confirming:
  - Jira receives HTTP 200 from the production endpoint.
  - The event is queued once.
  - The worker fetches the full Jira issue.
  - The `Customers` field maps to the correct dashboard partner.
  - Ticket creation, comments, and status/resolution changes stage in the month
    of the Jira event timestamp, not the month the worker processed the event.
  - Unknown customers are retained for mapping review instead of being assigned
    to the wrong partner.

### Observability

- Send application logs to CloudWatch.
- Add structured logs for auth and ingestion events.
- Track reset-email delivery success/failure.
- Add error monitoring before launch.
- Add health check endpoint for load balancer/container health.

### Networking And Access

- Decide whether the app is public internet-facing or VPN/internal only.
- Restrict database access to app/worker security groups.
- Store third-party connector credentials in Secrets Manager.
- If using S3, scope IAM permissions to the exact bucket/prefixes needed.

## Pre-Launch Acceptance Checklist

- `scripts/aws_prod_smoke_test.sh` passes against the production URL.
- Production database is migrated and backed up.
- Password reset emails are delivered through the chosen provider.
- No local-only files are tracked or deployed.
- App runs with `APP_ENV=production` and passes config validation.
- Web service and scheduler/worker service are separated.
- Login, sign-up, forgot password, reset password, logout, and dashboard routes
  are tested against the deployed environment.
- Secrets are managed outside git.
- Logs and alerts are visible to the maintainer.

## Open Decisions

- Final hosting choice: App Runner vs ECS Fargate vs another AWS target.
- Final email provider: Amazon SES vs SMTP provider.
- Database migration timing and target schema.
- Whether local password auth remains long-term or ARM SSO replaces it.
- Whether generated document storage should move to S3 immediately or after the
  first internal pilot.
