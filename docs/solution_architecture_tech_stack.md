# Solution Architecture And Tech Stack

Product: Cloud AI Software Ecosystem Updates
Source: `docs/product_requirements_document.md`
Version: Draft v1
Date: 2026-08-07

## 1. Architecture Goal

The goal is to turn the PRD into a product-grade technical design.

This document answers:

- What stack should be used.
- How the client should be organized.
- How the server should be organized.
- How workers and agents should behave.
- What PostgreSQL tables are required.
- What the primary keys and foreign keys are.
- Why each table and important column exists.
- How partner memory and cross-table analysis should work.
- How the system should stay clean without repeating data everywhere.

This is not a migration plan for the existing codebase. It is the target product
architecture I would design as the solution architect.

## 2. Naming Standard

Canonical app name:

- `Cloud AI Software Ecosystem Updates`

Technical slug:

- `cloud-ai-software-ecosystem-updates`

Use the canonical app name for screen titles, browser titles, Admin-visible app
labels, architecture diagrams, PRD references, runbooks, and generated technical
documents.

Use the technical slug for repository names, container images, service names,
queue/log/bucket prefixes, and CI/CD labels unless a specific infrastructure
length limit requires a shorter alias.

API title:

- `Cloud AI Software Ecosystem Updates API`

Core runtime names:

- Client: `cloud-ai-software-ecosystem-updates-web`
- Server/API: `cloud-ai-software-ecosystem-updates-api`
- Worker: `cloud-ai-software-ecosystem-updates-worker`
- Migrations: `cloud-ai-software-ecosystem-updates-migrations`

## 3. What A Technical Reviewer Should See Immediately

If a DevOps engineer, solution architect, or platform owner asks "what is the
architecture?", this product should have a crisp answer:

```text
Client
  Next.js web app for Contributor View, Presenter View, and Admin View.

API
  FastAPI service that owns auth, permissions, partner data, update lifecycle,
  connected source lifecycle, integration config, presenter analysis, and report
  requests.

Worker
  Python worker service that processes webhook/source jobs, runs extraction
  agents, generates report artifacts, and updates partner memory.

Database
  PostgreSQL is the relational source of truth for users, partners, metadata,
  connected sources, pending/approved updates, report metadata, and memory
  references.

Object Storage
  S3 stores generated artifacts, stored SharePoint file copies, and large source
  payload files where allowed.

Queue
  SQS decouples webhooks, extraction, report generation, and memory jobs from
  web requests.

Secrets
  Secrets Manager stores application secrets, integration credentials, default
  pilot password material, database credentials, and encryption keys.

Infrastructure
  ECS Fargate runs separate web and worker services behind an HTTPS entry point.
```

The boundaries should be easy to defend:

| Boundary | Owner | Responsibility |
| --- | --- | --- |
| Client | Web app | UI, forms, filters, view state, API calls. |
| API | Backend service | Business rules, authorization, validation, lifecycle transitions. |
| Worker | Backend worker | Slow/asynchronous processing, agents, report generation, memory jobs. |
| PostgreSQL | Database | Durable relational state and source of truth. |
| S3 | Storage | Durable file/artifact storage. |
| SQS | Queue | Reliable async processing and retries. |
| Secrets Manager | Secret store | Credentials and sensitive runtime configuration. |

The most important production rule is this:

> Web requests should change product state quickly and enqueue expensive work.
> Agents, document parsing, and report regeneration should run in workers.

## 4. Product Shape

The product has three visible views:

1. Contributor View
2. Presenter View
3. Admin View

The product has four backend workflows:

1. User/partner administration
2. Contributor update review
3. Connected source ingestion
4. Presenter analysis and report generation

The product has one source of truth:

- Approved Updates

Approved Updates drive:

- Presenter View
- Word monthly report
- Executive email draft
- Executive Summary
- Decision Board
- Partner memory

Partner Metadata is important context, but for v1 it does not feed reports,
email, Executive Summary, or Decision Board.

## 5. Recommended Tech Stack

### 5.1 Client

Recommended:

- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- shadcn/ui or a small internal component system
- TanStack Query only for client-heavy interactive areas if needed
- Zod for client-side form validation where useful

Why:

- The product is form-heavy and dashboard-heavy.
- Contributor/Admin screens need interactive forms.
- Presenter screens need filtered read-only data.
- TypeScript keeps the client honest as the product grows.
- A component system prevents every page from becoming custom one-off UI.

### 5.2 Server/API

Recommended:

- FastAPI
- Python 3.12
- Pydantic v2
- SQLAlchemy 2.x async ORM/Core
- Alembic migrations
- asyncpg PostgreSQL driver
- httpx for external calls
- boto3 or aioboto3 for AWS integrations

Why:

- The backend needs strong API boundaries.
- Python is suitable for document parsing and AI workflows.
- FastAPI supports modular routers and typed request/response models.
- SQLAlchemy plus Alembic gives production-grade schema evolution.

### 5.3 Database

Recommended:

- PostgreSQL 16+ or 17+
- RDS PostgreSQL or Aurora PostgreSQL in AWS
- pgvector extension for memory embeddings
- JSONB only for flexible source payload metadata, not for core relational fields

Why:

- The product is relational at its core: users, partners, sources, updates,
  reports.
- PostgreSQL gives relational integrity, JSONB escape hatches, indexing, and
  vector extension support.
- Do not start with SQLite for this target architecture.

### 5.4 Queue And Background Work

Recommended:

- Amazon SQS for source-event and generation jobs
- Dead-letter queues for failed processing
- EventBridge only for scheduled/system-triggered jobs if needed later
- Worker service running the same backend codebase with different entrypoint

Why:

- Webhooks should return quickly.
- AI/document processing should not block web requests.
- Report regeneration after approval should run outside the user request path
  when needed.
- Failed events need retry and isolation.

### 5.5 Storage

Recommended:

- Amazon S3 for files/artifacts
- Server-side encryption
- Private buckets
- Signed URLs only where necessary

Used for:

- Stored SharePoint file copies
- Generated Word reports
- Generated email draft artifacts
- Optional raw payload exports
- Any future document attachments

### 5.6 Auth

First pass:

- Email + shared configured default password.
- Admin-created users.
- Default password stored as secret/config, not visible in the app.

Future:

- ARM SSO / OIDC.
- Disable password login completely when SSO is active.

### 5.7 Deployment

Recommended:

- ECS Fargate
- One web service
- One worker service
- RDS/Aurora PostgreSQL
- S3
- SQS + DLQ
- Secrets Manager
- CloudWatch Logs

## 6. Top-Level Repository Layout

Target repository:

```text
cloud-ai-software-ecosystem-updates/
  apps/
    web/
      src/
        app/
        components/
        features/
        lib/
        styles/
        types/

    api/
      app/
        main.py
        core/
        db/
        domains/
        integrations/
        agents/
        storage/
        queue/
        workers/

  infra/
    terraform/ or cdk/

  docs/
    product_requirements_document.md
    solution_architecture_tech_stack.md
    api_contract.md
    data_model.md
    runbooks/

  tests/
    api/
    worker/
    e2e/
```

Do not start with microservices. Start with a modular monorepo:

- One frontend app.
- One backend API.
- One worker process.
- One shared database.

This is a modular monolith with clear boundaries.

## 7. Client-Side Design

### 7.1 Client App Responsibilities

The client should:

- Render Contributor View, Presenter View, and Admin View.
- Call typed API endpoints.
- Maintain UI state for filters, forms, tabs, and modals.
- Avoid embedding business rules that belong on the server.
- Use server-returned permissions to decide visible actions.

The client should not:

- Own approval logic.
- Own source status transitions.
- Run rulebooks.
- Generate reports directly.
- Store secrets.
- Call Jira/Slack/SharePoint/Confluence/GitHub directly.

### 7.2 Client Feature Structure

```text
apps/web/src/
  app/
    login/
      page.tsx
    contributor/
      page.tsx
    presenter/
      page.tsx
    admin/
      page.tsx
    layout.tsx

  features/
    auth/
      LoginForm.tsx
      auth-api.ts

    contributor/
      ContributorShell.tsx
      PartnerSelector.tsx
      PendingUpdatesTab.tsx
      PartnerMetadataTab.tsx
      ApprovedUpdatesTab.tsx
      ConnectedSourcesTab.tsx

    metadata/
      StatusField.tsx
      GoalsEditor.tsx
      RisksIssuesTable.tsx
      ResourceLinksEditor.tsx
      metadata-api.ts

    updates/
      PendingUpdateCard.tsx
      ApprovedUpdateList.tsx
      ManualUpdateForm.tsx
      UpdateFilters.tsx
      updates-api.ts

    connected-sources/
      ConnectedSourceList.tsx
      ConnectedSourceCreateDialog.tsx
      JiraSourceForm.tsx
      SlackSourceForm.tsx
      SharePointSourceForm.tsx
      ConfluenceSourceForm.tsx
      GitHubSourceForm.tsx
      connected-sources-api.ts

    presenter/
      PresenterShell.tsx
      PresenterFilters.tsx
      PresenterMetadataPanel.tsx
      PresenterApprovedUpdates.tsx
      ExecutiveSummaryPanel.tsx
      DecisionBoardPanel.tsx
      ReportActions.tsx
      presenter-api.ts

    admin/
      AdminShell.tsx
      UsersAdmin.tsx
      PartnersAdmin.tsx
      IntegrationsAdmin.tsx
      ConnectedSourceApprovals.tsx
      admin-api.ts

  components/
    ui/
      Button.tsx
      Input.tsx
      Select.tsx
      Dialog.tsx
      Table.tsx
      Badge.tsx
      Tabs.tsx
      Toast.tsx
    layout/
      AppNav.tsx
      PageHeader.tsx
      EmptyState.tsx
      ErrorState.tsx
      LoadingState.tsx

  lib/
    api-client.ts
    routes.ts
    dates.ts
    permissions.ts

  types/
    api.ts
    domain.ts
```

### 7.3 Approximate Client File Count

This should not be one giant dashboard file.

Expected first clean client:

| Area | Approx files |
| --- | ---: |
| App routes/layout | 5 |
| Shared UI/layout components | 12-18 |
| Auth | 2-4 |
| Contributor feature | 10-14 |
| Metadata feature | 5-8 |
| Updates feature | 5-8 |
| Connected Sources feature | 8-12 |
| Presenter feature | 8-12 |
| Admin feature | 8-12 |
| API clients/types/utils | 8-12 |

Expected total:

- About 70-100 small files.

That sounds like more files, but the point is that each file is easy to
understand. World-class codebases prefer small, named pieces over one file with
everything.

## 8. Server-Side Design

### 8.1 Server Responsibilities

The server should:

- Authenticate users.
- Authorize every action.
- Own all business rules.
- Own source lifecycle transitions.
- Own update lifecycle transitions.
- Own report generation.
- Own integration credentials.
- Provide typed JSON APIs to the client.
- Receive webhooks.
- Enqueue background work.

The server should not:

- Render HTML in the target architecture.
- Keep UI state.
- Let client directly mutate database semantics.
- Let client decide whether a source is active.

### 8.2 Backend Module Layout

```text
apps/api/app/
  main.py

  core/
    config.py
    logging.py
    security.py
    permissions.py
    errors.py
    clock.py

  db/
    session.py
    base.py
    migrations/
    models/
      identity.py
      partners.py
      metadata.py
      sources.py
      updates.py
      reports.py
      memory.py
      audit.py

  domains/
    identity/
      router.py
      service.py
      repository.py
      schemas.py

    partners/
      router.py
      service.py
      repository.py
      schemas.py

    metadata/
      router.py
      service.py
      repository.py
      schemas.py

    resource_links/
      router.py
      service.py
      repository.py
      schemas.py

    connected_sources/
      router.py
      service.py
      repository.py
      schemas.py
      validators.py

    updates/
      router.py
      service.py
      repository.py
      schemas.py

    presenter/
      router.py
      service.py
      schemas.py

    reports/
      router.py
      service.py
      repository.py
      schemas.py

    admin/
      router.py
      service.py
      schemas.py

  integrations/
    jira/
      webhook.py
      client.py
      normalizer.py
      tester.py
    slack/
      webhook.py
      client.py
      normalizer.py
      tester.py
    sharepoint/
      client.py
      normalizer.py
      tester.py
    confluence/
      client.py
      normalizer.py
      tester.py
    github/
      webhook.py
      client.py
      normalizer.py
      tester.py

  agents/
    rulebooks/
      update_extraction/
        jira.md
        slack.md
        sharepoint.md
        confluence.md
        github.md
      reporting/
        executive_email.md
        executive_summary.md
        decision_board.md
    extraction_agent.py
    presenter_agent.py
    report_agent.py
    schemas.py

  storage/
    base.py
    s3.py
    local.py

  queue/
    base.py
    sqs.py
    local.py
    messages.py

  workers/
    main.py
    source_event_worker.py
    report_generation_worker.py
    memory_worker.py
```

### 8.3 API Boundary

The API should expose domain-specific endpoints:

```text
Auth
  POST /api/auth/login
  POST /api/auth/logout
  GET  /api/auth/me

Contributor
  GET  /api/contributor/partners
  GET  /api/contributor/partners/{partner_id}/dashboard

Metadata
  GET  /api/partners/{partner_id}/metadata?cycle=YYYY-MM
  PUT  /api/partners/{partner_id}/metadata
  POST /api/partners/{partner_id}/resource-links
  PUT  /api/resource-links/{resource_link_id}
  DELETE /api/resource-links/{resource_link_id}

Pending/Approved Updates
  GET  /api/partners/{partner_id}/pending-updates
  POST /api/partners/{partner_id}/pending-updates/manual
  POST /api/pending-updates/{update_id}/approve
  POST /api/pending-updates/{update_id}/reject
  PUT  /api/pending-updates/{update_id}
  GET  /api/partners/{partner_id}/approved-updates

Connected Sources
  GET  /api/partners/{partner_id}/connected-sources
  POST /api/partners/{partner_id}/connected-sources
  POST /api/connected-sources/{source_id}/pause
  POST /api/connected-sources/{source_id}/resume
  POST /api/connected-sources/{source_id}/resubmit

Presenter
  GET  /api/presenter/dashboard
  GET  /api/presenter/approved-updates
  POST /api/presenter/executive-summary
  POST /api/presenter/decision-board
  POST /api/reports/monthly-word/generate
  GET  /api/reports/monthly-word/{cycle}/download
  POST /api/reports/executive-email/generate
  GET  /api/reports/executive-email/{cycle}/download

Admin
  GET  /api/admin/users
  POST /api/admin/users
  PUT  /api/admin/users/{user_id}
  POST /api/admin/users/{user_id}/deactivate
  POST /api/admin/users/{user_id}/reactivate
  GET  /api/admin/partners
  POST /api/admin/partners
  PUT  /api/admin/partners/{partner_id}
  POST /api/admin/partners/{partner_id}/archive
  GET  /api/admin/integrations
  PUT  /api/admin/integrations/{integration_type}/credentials
  POST /api/admin/integrations/{integration_type}/test
  GET  /api/admin/connected-source-approvals
  POST /api/admin/connected-sources/{source_id}/approve
  POST /api/admin/connected-sources/{source_id}/reject

Webhooks
  POST /api/webhooks/jira
  POST /api/webhooks/slack
  POST /api/webhooks/github
  POST /api/webhooks/confluence
  POST /api/webhooks/sharepoint
```

## 9. Database Design Principles

### 9.1 Key Choices

Use UUID primary keys for product entities.

Reasons:

- Safer public references than sequential integers.
- Better for event-driven systems.
- Easier to merge/import data.
- Still fine for this scale with proper indexing.

Use `created_at` and `updated_at` on most mutable business tables.

Use `deleted_at` or status fields instead of hard delete where history matters.

### 9.2 Avoiding Repetition

Do not duplicate partner names on update rows.

Instead:

- `updates.partner_id` references `partners.partner_id`.

Do not duplicate contributor names on partner rows.

Instead:

- `partner_assignments.user_id` references `users.user_id`.

Do not duplicate connected source details on update rows.

Instead:

- `updates.connected_source_id` references `connected_sources.connected_source_id`.

Do not store report content in multiple places.

Instead:

- Store generated artifact file in S3.
- Store artifact metadata in `report_artifacts`.

### 9.3 JSONB Use

Use JSONB only for:

- Raw external payloads
- Provider-specific metadata
- Test result details
- Agent structured outputs

Do not use JSONB for:

- User roles
- Partner ownership
- Approved updates
- Metadata fields
- Connected source status
- Report artifact state

Core business data should stay relational.

### 9.4 Indexing Rules

Index every foreign key used in joins.

Index every filter used by main screens:

- `partner_id`
- `cycle`
- `status`
- `source_type`
- `approved_at`
- `created_at`

Use partial unique indexes for business constraints where applicable.

## 10. PostgreSQL Schema

Recommended schemas:

```sql
app
```

Optionally split later:

```sql
identity
partner
ingestion
reporting
memory
audit
```

For first pass, a single `app` schema is simpler.

## 11. Enum Types

Recommended PostgreSQL enums:

```text
role_type
  contributor
  presenter
  admin

partner_status
  active
  archived

metadata_status
  on_track
  at_risk
  blocked

integration_type
  jira
  slack
  sharepoint
  confluence
  github

integration_status
  not_configured
  configured
  enabled
  failed
  disabled

connected_source_status
  pending
  needs_access_setup
  active
  disabled
  rejected
  failed

connected_source_type
  jira_issue
  slack_channel
  sharepoint_file
  confluence_page
  github_repository
  github_issue
  github_pull_request

update_status
  pending
  approved
  rejected

source_type
  manual
  jira
  slack
  sharepoint
  confluence
  github

report_type
  monthly_word
  executive_email

job_status
  queued
  running
  succeeded
  failed
  retrying
```

## 12. Tables

### 12.1 `users`

Purpose:

Stores application users independently of auth provider.

Primary key:

- `user_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| user_id | uuid | PK | Stable internal user identity. |
| email | citext | unique | Login identifier and business identity. |
| display_name | text | | Name shown in UI. |
| status | text | indexed | Active/deactivated user state. |
| created_at | timestamptz | | Audit. |
| updated_at | timestamptz | | Audit. |
| deactivated_at | timestamptz | nullable | Preserve history when access removed. |

Notes:

- Use `citext` or lowercased unique index for case-insensitive email.
- Do not store role booleans here. Use `user_role_assignments`.

### 12.2 `user_role_assignments`

Purpose:

Supports multiple role capabilities per user.

Primary key:

- `(user_id, role_type)`

Foreign keys:

- `user_id` references `users.user_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| user_id | uuid | PK, FK | User receiving capability. |
| role_type | role_type | PK | contributor, presenter, admin. |
| assigned_by | uuid | FK users.user_id, nullable | Who granted role. |
| assigned_at | timestamptz | | Audit. |

Notes:

- Admin role should be bootstrap/config protected in product policy.
- Table still supports admin role technically, but service layer blocks casual assignment.

### 12.3 `user_sessions`

Purpose:

Server-side session tracking.

Primary key:

- `session_id`

Foreign keys:

- `user_id` references `users.user_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| session_id | uuid | PK | Session identity. |
| user_id | uuid | FK | Authenticated user. |
| created_at | timestamptz | | Session audit. |
| expires_at | timestamptz | indexed | Expiration. |
| revoked_at | timestamptz | nullable | Logout/revoke. |
| user_agent_hash | text | nullable | Security/debugging without full user agent. |

### 12.4 `partners`

Purpose:

Stores partner identity.

Primary key:

- `partner_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| partner_id | uuid | PK | Stable partner identity. |
| name | text | unique indexed | Display name. |
| website | text | nullable | Basic partner identity. |
| color | text | nullable | UI identity. |
| status | partner_status | indexed | Active/archive state. |
| created_by | uuid | FK users.user_id | Admin who created partner. |
| created_at | timestamptz | | Audit. |
| updated_at | timestamptz | | Audit. |
| archived_at | timestamptz | nullable | Archive timestamp. |

### 12.5 `partner_assignments`

Purpose:

Represents exactly one assigned contributor per active partner.

Primary key:

- `partner_id`

Foreign keys:

- `partner_id` references `partners.partner_id`
- `user_id` references `users.user_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| partner_id | uuid | PK, FK | Partner being assigned. |
| user_id | uuid | FK indexed | Contributor owner. |
| assigned_by | uuid | FK users.user_id | Admin assigning owner. |
| assigned_at | timestamptz | | Audit. |

Notes:

- Primary key on `partner_id` enforces one contributor per partner.
- Index `user_id` to list all partners owned by a contributor.

### 12.6 `partner_metadata_snapshots`

Purpose:

Stores monthly partner metadata snapshot.

Primary key:

- `metadata_snapshot_id`

Unique key:

- `(partner_id, cycle)`

Foreign keys:

- `partner_id` references `partners.partner_id`
- `saved_by` references `users.user_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| metadata_snapshot_id | uuid | PK | Snapshot identity. |
| partner_id | uuid | FK indexed | Metadata belongs to partner. |
| cycle | date | indexed | Month snapshot, stored as first day of month. |
| status | metadata_status | indexed | On Track, At Risk, Blocked. |
| highlights_text | text | | Free-text highlights/status. |
| business_priority_text | text | | Free-text business priority. |
| saved_by | uuid | FK | Contributor who saved. |
| saved_at | timestamptz | | Last save timestamp. |
| created_at | timestamptz | | Audit. |
| updated_at | timestamptz | | Audit. |

Notes:

- Multiple saves in same month update the same row.
- No intra-month version history.

### 12.7 `partner_metadata_goals`

Purpose:

Stores bullet-list goals for a monthly metadata snapshot.

Primary key:

- `goal_id`

Foreign keys:

- `metadata_snapshot_id` references `partner_metadata_snapshots.metadata_snapshot_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| goal_id | uuid | PK | Goal row identity. |
| metadata_snapshot_id | uuid | FK indexed | Parent monthly snapshot. |
| position | int | | Bullet order. |
| goal_text | text | | Goal content. |

Notes:

- Replace rows on save for simple "latest for month" behavior.

### 12.8 `partner_metadata_risks`

Purpose:

Stores Key Risks & Issues table rows for a monthly metadata snapshot.

Primary key:

- `risk_id`

Foreign keys:

- `metadata_snapshot_id` references `partner_metadata_snapshots.metadata_snapshot_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| risk_id | uuid | PK | Risk row identity. |
| metadata_snapshot_id | uuid | FK indexed | Parent monthly snapshot. |
| position | int | | Display order/item number. |
| description | text | | Risk/issue description. |
| go_to_green_action | text | nullable | Recovery action. |
| severity | text | nullable | Severity value as displayed. |
| assigned_owner | text | nullable | Owner name/free text. |
| due_date | date | nullable | Due date. |
| ramification | text | nullable | Impact if unresolved. |

### 12.9 `partner_resource_links`

Purpose:

Stores convenience links on Partner Metadata.

Primary key:

- `resource_link_id`

Foreign keys:

- `partner_id` references `partners.partner_id`
- `connected_source_id` references `connected_sources.connected_source_id`, nullable
- `created_by` references `users.user_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| resource_link_id | uuid | PK | Link identity. |
| partner_id | uuid | FK indexed | Partner owning link. |
| title | text | | Link display title. |
| url | text | | Actual resource URL. |
| description | text | nullable | Optional context. |
| connected_source_id | uuid | FK nullable | Tracks auto-created link from source. |
| is_disabled | boolean | | Show disabled/inactive if needed. |
| created_by | uuid | FK | Contributor/system creator. |
| created_at | timestamptz | | Audit. |
| updated_at | timestamptz | | Audit. |

Notes:

- Removing resource link does not remove Connected Source.
- `connected_source_id` is nullable because many links are manual convenience links.

### 12.10 `integrations`

Purpose:

Stores global integration status by integration type.

Primary key:

- `integration_id`

Unique key:

- `integration_type`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| integration_id | uuid | PK | Integration row identity. |
| integration_type | integration_type | unique | Jira, Slack, etc. |
| status | integration_status | indexed | Global setup/test state. |
| enabled_at | timestamptz | nullable | When test passed/enabled. |
| disabled_at | timestamptz | nullable | Admin disabled. |
| last_tested_at | timestamptz | nullable | Last connection test. |
| last_test_status | text | nullable | Quick status. |
| last_error_summary | text | nullable | Admin-visible summary. |
| created_at | timestamptz | | Audit. |
| updated_at | timestamptz | | Audit. |

### 12.11 `integration_secrets`

Purpose:

Stores encrypted integration secrets entered in Admin UI.

Primary key:

- `integration_secret_id`

Foreign keys:

- `integration_id` references `integrations.integration_id`
- `updated_by` references `users.user_id`

Unique key:

- `(integration_id, secret_name)`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| integration_secret_id | uuid | PK | Secret row identity. |
| integration_id | uuid | FK indexed | Parent integration. |
| secret_name | text | | e.g. bot_token, webhook_secret. |
| ciphertext | text | | Encrypted value. |
| value_fingerprint | text | nullable | Compare rotations without revealing secret. |
| updated_by | uuid | FK | Admin who saved/replaced. |
| updated_at | timestamptz | | Rotation audit. |

Notes:

- Never show saved secret values.
- Admin can replace/rotate only.

### 12.12 `integration_test_runs`

Purpose:

Records global integration connection tests.

Primary key:

- `test_run_id`

Foreign keys:

- `integration_id` references `integrations.integration_id`
- `run_by` references `users.user_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| test_run_id | uuid | PK | Test identity. |
| integration_id | uuid | FK indexed | Integration tested. |
| status | job_status | indexed | succeeded/failed/running. |
| run_by | uuid | FK nullable | Admin or system. |
| started_at | timestamptz | | Timing. |
| finished_at | timestamptz | nullable | Timing. |
| result_summary | text | nullable | Admin-readable result. |
| result_details | jsonb | nullable | Technical details. |

### 12.13 `connected_sources`

Purpose:

Stores contributor-submitted partner-specific active/pending source mappings.

Primary key:

- `connected_source_id`

Foreign keys:

- `partner_id` references `partners.partner_id`
- `integration_id` references `integrations.integration_id`
- `created_by` references `users.user_id`
- `approved_by` references `users.user_id`, nullable

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| connected_source_id | uuid | PK | Source identity. |
| partner_id | uuid | FK indexed | Partner owning source. |
| integration_id | uuid | FK indexed | Global integration dependency. |
| source_type | connected_source_type | indexed | Jira issue, Slack channel, etc. |
| status | connected_source_status | indexed | Pending/active/rejected/etc. |
| display_name | text | nullable | Auto-generated or source title. |
| source_url | text | nullable indexed | Link when source is URL-based. |
| external_identifier | text | nullable indexed | Issue key, channel ID, repo full name, etc. |
| created_by | uuid | FK | Contributor who requested. |
| approved_by | uuid | FK nullable | Admin who approved. |
| approved_at | timestamptz | nullable | Approval timestamp. |
| rejected_at | timestamptz | nullable | Rejection timestamp. |
| disabled_at | timestamptz | nullable | Archived/disabled timestamp. |
| last_tested_at | timestamptz | nullable | Last source-specific test. |
| last_error_summary | text | nullable | Admin-visible error summary. |
| created_at | timestamptz | | Audit. |
| updated_at | timestamptz | | Audit. |

Notes:

- Common fields live here.
- Type-specific fields live in child tables below.

### 12.14 `connected_source_jira_issues`

Purpose:

Stores Jira single-issue specific fields.

Primary key:

- `connected_source_id`

Foreign keys:

- `connected_source_id` references `connected_sources.connected_source_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| connected_source_id | uuid | PK, FK | One-to-one with source. |
| issue_key | text | indexed | e.g. SPEAR-1234. |
| issue_url | text | | Main Jira issue URL. |

### 12.15 `connected_source_slack_channels`

Purpose:

Stores Slack channel-specific fields.

Primary key:

- `connected_source_id`

Foreign keys:

- `connected_source_id` references `connected_sources.connected_source_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| connected_source_id | uuid | PK, FK | One-to-one with source. |
| channel_name | text | | Contributor-entered readable channel name. |
| channel_id | text | unique indexed | Slack channel ID. |
| bot_invited_confirmed | boolean | | Contributor confirmation checkbox. |

Notes:

- Unique `channel_id` enforces one Slack channel maps to one partner.

### 12.16 `connected_source_sharepoint_files`

Purpose:

Stores SharePoint single-file specific fields.

Primary key:

- `connected_source_id`

Foreign keys:

- `connected_source_id` references `connected_sources.connected_source_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| connected_source_id | uuid | PK, FK | One-to-one with source. |
| file_url | text | | Contributor-entered file URL. |
| drive_item_id | text | nullable indexed | Provider ID after resolution. |
| file_name | text | nullable | Detected file name. |
| file_type | text | nullable | docx, pptx, xlsx, pdf. |

### 12.17 `connected_source_confluence_pages`

Purpose:

Stores Confluence single-page specific fields.

Primary key:

- `connected_source_id`

Foreign keys:

- `connected_source_id` references `connected_sources.connected_source_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| connected_source_id | uuid | PK, FK | One-to-one with source. |
| page_url | text | | Contributor-entered page URL. |
| page_id | text | nullable indexed | Provider page ID. |
| page_title | text | nullable | Detected page title. |

### 12.18 `connected_source_github_targets`

Purpose:

Stores GitHub repo/issue/PR specific fields.

Primary key:

- `connected_source_id`

Foreign keys:

- `connected_source_id` references `connected_sources.connected_source_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| connected_source_id | uuid | PK, FK | One-to-one with source. |
| github_url | text | | Contributor-entered URL. |
| owner | text | indexed | GitHub owner/org. |
| repo | text | indexed | GitHub repository. |
| object_type | text | | repository, issue, pull_request. |
| object_number | int | nullable | Issue/PR number if applicable. |

### 12.19 `connected_source_test_runs`

Purpose:

Records source-specific tests after Admin approval.

Primary key:

- `source_test_run_id`

Foreign keys:

- `connected_source_id` references `connected_sources.connected_source_id`
- `run_by` references `users.user_id`, nullable

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| source_test_run_id | uuid | PK | Test identity. |
| connected_source_id | uuid | FK indexed | Source being tested. |
| status | job_status | indexed | succeeded/failed. |
| run_by | uuid | FK nullable | Admin/system trigger. |
| started_at | timestamptz | | Timing. |
| finished_at | timestamptz | nullable | Timing. |
| result_summary | text | nullable | Admin-readable result. |
| result_details | jsonb | nullable | Technical diagnostic details. |

### 12.20 `storage_objects`

Purpose:

Stores metadata for files in S3.

Primary key:

- `storage_object_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| storage_object_id | uuid | PK | Storage metadata identity. |
| bucket | text | | S3 bucket. |
| object_key | text | unique | S3 object key. |
| content_type | text | nullable | MIME type. |
| file_name | text | nullable | Original/display file name. |
| byte_size | bigint | nullable | File size. |
| checksum_sha256 | text | nullable indexed | Integrity/dedupe. |
| created_at | timestamptz | | Audit. |

### 12.21 `source_events`

Purpose:

Stores normalized source events that may produce Pending Updates.

Primary key:

- `source_event_id`

Foreign keys:

- `connected_source_id` references `connected_sources.connected_source_id`
- `partner_id` references `partners.partner_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| source_event_id | uuid | PK | Event identity. |
| connected_source_id | uuid | FK indexed | Source that produced event. |
| partner_id | uuid | FK indexed | Denormalized for efficient partner queries but still FK. |
| source_type | source_type | indexed | Jira/Slack/etc. |
| external_event_id | text | nullable indexed | Provider event ID if available. |
| source_url | text | nullable indexed | URL used on generated update. |
| source_event_timestamp | timestamptz | indexed | Source timestamp for cycle assignment. |
| technical_metadata | jsonb | nullable | IDs/timestamps/no-content metadata. |
| processing_status | job_status | indexed | Event processing lifecycle. |
| received_at | timestamptz | | Webhook/ingestion receive time. |

Notes:

- Slack stores technical metadata only, no raw text.
- `partner_id` is copied from source mapping for performance, but it remains
  consistent through FK and service rules.

### 12.22 `source_payloads`

Purpose:

Stores raw source payload/content when allowed.

Primary key:

- `source_payload_id`

Foreign keys:

- `source_event_id` references `source_events.source_event_id`
- `storage_object_id` references `storage_objects.storage_object_id`, nullable

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| source_payload_id | uuid | PK | Payload identity. |
| source_event_id | uuid | FK unique | One payload record per event. |
| raw_payload_json | jsonb | nullable | Jira/GitHub/Confluence structured raw content. |
| raw_text_encrypted | text | nullable | Raw text if needed and allowed. |
| storage_object_id | uuid | FK nullable | SharePoint file copy or large payload. |
| retention_policy | text | | Tracks source-specific retention behavior. |
| created_at | timestamptz | | Audit. |

Notes:

- No Slack raw message content should be stored here.

### 12.23 `agent_runs`

Purpose:

Tracks agent/model processing for extraction, analysis, and reports.

Primary key:

- `agent_run_id`

Foreign keys:

- `source_event_id` references `source_events.source_event_id`, nullable
- `triggered_by` references `users.user_id`, nullable

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| agent_run_id | uuid | PK | Agent run identity. |
| run_type | text | indexed | extraction, email, summary, decision_board. |
| source_event_id | uuid | FK nullable | Source event for extraction. |
| model_name | text | nullable | Model/deployment used. |
| rulebook_name | text | | Which developer-owned rulebook was used. |
| rulebook_version | text | nullable | Version/hash. |
| status | job_status | indexed | Run status. |
| input_fingerprint | text | nullable | Debug/dedupe without storing prompt. |
| output_json | jsonb | nullable | Structured model output if safe. |
| error_summary | text | nullable | Debug summary. |
| triggered_by | uuid | FK nullable | User/system trigger. |
| started_at | timestamptz | | Timing. |
| finished_at | timestamptz | nullable | Timing. |

Notes:

- Do not store sensitive raw prompts unless policy allows it.
- Store fingerprints/versioning for auditability.

### 12.24 `updates`

Purpose:

Stores Pending, Approved, and Rejected Updates in one lifecycle table.

Primary key:

- `update_id`

Foreign keys:

- `partner_id` references `partners.partner_id`
- `connected_source_id` references `connected_sources.connected_source_id`, nullable
- `source_event_id` references `source_events.source_event_id`, nullable
- `created_by` references `users.user_id`, nullable
- `approved_by` references `users.user_id`, nullable

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| update_id | uuid | PK | Update identity. |
| partner_id | uuid | FK indexed | Partner. |
| status | update_status | indexed | Pending/approved/rejected. |
| update_text | text | | Current/final update text. |
| text_hash | text | indexed | Exact duplicate detection. |
| source_type | source_type | indexed | Manual/Jira/Slack/etc. |
| connected_source_id | uuid | FK nullable indexed | Source mapping, null for manual. |
| source_event_id | uuid | FK nullable indexed | Source event, null for manual. |
| source_url | text | nullable indexed | One source link, null for manual. |
| cycle | date | indexed | Month, stored as first day of month. |
| created_by | uuid | FK nullable | Contributor for manual or system user. |
| approved_by | uuid | FK nullable | Assigned contributor approving. |
| created_at | timestamptz | indexed | Pending creation time. |
| updated_at | timestamptz | | Latest pending edit time. |
| approved_at | timestamptz | nullable indexed | Official approval timestamp. |
| rejected_at | timestamptz | nullable | Rejection timestamp. |

Important indexes:

```text
idx_updates_partner_status_cycle
  (partner_id, status, cycle)

idx_updates_approved_cycle_partner
  (cycle, partner_id)
  WHERE status = 'approved'

unique_exact_source_text
  (source_url, text_hash)
  WHERE source_url IS NOT NULL
```

Notes:

- One table avoids duplicating Pending and Approved update text.
- Approved rows are immutable by service-layer rule.
- Manual updates have `source_type = manual`, `source_url = null`.

### 12.25 `report_artifacts`

Purpose:

Stores latest generated report/email artifact metadata per month.

Primary key:

- `report_artifact_id`

Unique key:

- `(report_type, cycle)`

Foreign keys:

- `storage_object_id` references `storage_objects.storage_object_id`
- `generated_by` references `users.user_id`, nullable

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| report_artifact_id | uuid | PK | Artifact identity. |
| report_type | report_type | unique part | Word or executive email. |
| cycle | date | unique part indexed | Month artifact belongs to. |
| storage_object_id | uuid | FK | Stored file artifact. |
| source_data_hash | text | indexed | Hash of approved updates used. |
| generated_by | uuid | FK nullable | Presenter or system. |
| generated_at | timestamptz | | Generation time. |
| status | job_status | indexed | succeeded/failed/retrying. |

Notes:

- Regeneration overwrites by updating the same `(report_type, cycle)` record and
  replacing `storage_object_id`.

### 12.26 `report_generation_runs`

Purpose:

Tracks report/email generation attempts and retries.

Primary key:

- `report_generation_run_id`

Foreign keys:

- `report_artifact_id` references `report_artifacts.report_artifact_id`, nullable
- `triggered_by` references `users.user_id`, nullable

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| report_generation_run_id | uuid | PK | Run identity. |
| report_artifact_id | uuid | FK nullable | Existing artifact if any. |
| report_type | report_type | indexed | Word/email. |
| cycle | date | indexed | Month. |
| trigger_reason | text | | presenter_request, update_approved, retry. |
| status | job_status | indexed | Run state. |
| attempt_number | int | | Retry count. |
| error_summary | text | nullable | Admin/debug. |
| triggered_by | uuid | FK nullable | Presenter/system. |
| started_at | timestamptz | | Timing. |
| finished_at | timestamptz | nullable | Timing. |

### 12.27 `memory_chunks`

Purpose:

Stores vector-searchable memory created from Approved Updates.

Primary key:

- `memory_chunk_id`

Foreign keys:

- `partner_id` references `partners.partner_id`
- `update_id` references `updates.update_id`

Unique key:

- `update_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| memory_chunk_id | uuid | PK | Memory chunk identity. |
| partner_id | uuid | FK indexed | Partner memory belongs to. |
| update_id | uuid | FK unique | One memory chunk per approved update. |
| cycle | date | indexed | Month of update. |
| memory_text | text | | Approved update text. |
| embedding | vector | indexed | Semantic retrieval. |
| embedding_model | text | | Model used. |
| created_at | timestamptz | | Audit. |

Notes:

- Source of truth remains `updates`.
- `memory_text` is a derived copy of approved update text for retrieval. This is
  an intentional read-optimized derivative, not a second source of truth.

### 12.28 `partner_memory_summaries`

Purpose:

Stores derived partner-level memory summaries for fast context.

Primary key:

- `partner_id`

Foreign keys:

- `partner_id` references `partners.partner_id`

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| partner_id | uuid | PK, FK | Partner being summarized. |
| summary_text | text | | Derived partner memory summary. |
| source_update_count | int | | Number of approved updates summarized. |
| source_max_approved_at | timestamptz | | Freshness check. |
| generated_at | timestamptz | | Generation time. |
| agent_run_id | uuid | FK agent_runs.agent_run_id nullable | Generation trace. |

Notes:

- Cache only. Can be regenerated from Approved Updates and memory chunks.

### 12.29 `audit_log`

Purpose:

Stores important user/system actions.

Primary key:

- `audit_log_id`

Foreign keys:

- `actor_user_id` references `users.user_id`, nullable

Columns:

| Column | Type | Key | Why needed |
| --- | --- | --- | --- |
| audit_log_id | uuid | PK | Audit row identity. |
| actor_user_id | uuid | FK nullable indexed | User/system actor. |
| action | text | indexed | e.g. update.approved, source.approved. |
| entity_type | text | indexed | Table/domain acted on. |
| entity_id | uuid | indexed | Entity identifier. |
| partner_id | uuid | FK partners.partner_id nullable indexed | Partner context. |
| occurred_at | timestamptz | indexed | Audit time. |
| metadata | jsonb | nullable | Non-secret details. |

Notes:

- Do not store secrets or raw Slack text in audit metadata.

## 13. Table Relationship Summary

```text
users
  -> user_role_assignments
  -> user_sessions
  -> partner_assignments

partners
  -> partner_assignments
  -> partner_metadata_snapshots
       -> partner_metadata_goals
       -> partner_metadata_risks
  -> partner_resource_links
  -> connected_sources
  -> updates
  -> memory_chunks
  -> partner_memory_summaries

integrations
  -> integration_secrets
  -> integration_test_runs
  -> connected_sources

connected_sources
  -> connected_source_jira_issues
  -> connected_source_slack_channels
  -> connected_source_sharepoint_files
  -> connected_source_confluence_pages
  -> connected_source_github_targets
  -> connected_source_test_runs
  -> source_events
  -> updates

source_events
  -> source_payloads
  -> agent_runs
  -> updates

updates
  -> memory_chunks
  -> report_generation_runs through generated artifacts indirectly

storage_objects
  -> source_payloads
  -> report_artifacts

report_artifacts
  -> report_generation_runs
```

## 14. Main Query Patterns

### 14.1 Contributor Partner List

Input:

- current user

Query:

- `partner_assignments` by `user_id`
- join `partners`

### 14.2 Contributor Pending Updates

Input:

- partner
- source type filter
- cycle filter

Query:

- `updates`
- where `partner_id = ?`
- `status = pending`
- optional `source_type`
- optional `cycle`
- order by `created_at desc`

### 14.3 Contributor Approved Updates

Input:

- partner
- source type filter
- cycle filter

Query:

- `updates`
- where `partner_id = ?`
- `status = approved`
- optional `source_type`
- optional `cycle`
- order by `approved_at desc`

### 14.4 Presenter Approved Updates

Input:

- selected partners
- cycle

Query:

- `updates`
- where `status = approved`
- `cycle = ?`
- `partner_id in (...)`
- order by partner name, approved timestamp

### 14.5 Word Report

Input:

- cycle

Query:

- all `updates`
- where `status = approved`
- `cycle = ?`
- join partner for grouping/display

### 14.6 Executive Email

Input:

- cycle

Query:

- same approved updates as Word report
- pass to email agent with developer-owned rulebook

### 14.7 Executive Summary

Input:

- selected partners
- cycle

Query:

- approved updates only
- selected partners
- selected cycle
- pass to presenter agent

### 14.8 Decision Board

Input:

- selected partners
- cycle

Query:

- approved updates only
- selected partners
- selected cycle
- pass to presenter agent/rulebook looking for risks, blockers, asks, deadlines

### 14.9 Partner Memory

Input:

- partner
- optional query

Query:

- retrieve approved updates from `updates`
- retrieve semantic matches from `memory_chunks`
- optionally include `partner_memory_summaries` for cached context

## 15. Partner Memory Design

### 15.1 Source Of Truth

Partner memory should be based on Approved Updates.

Do not use:

- Pending Updates
- raw Slack text
- raw hidden source content directly
- Partner Metadata for v1 analysis/reporting memory

### 15.2 Memory Write Flow

When update is approved:

1. Update row becomes `status = approved`.
2. System creates or updates one `memory_chunks` row for that update.
3. Worker computes embedding for approved update text.
4. Optional partner memory summary is marked stale.
5. Report regeneration job is queued immediately.

### 15.3 Memory Read Flow

For AI assistant or future cross-table analysis:

1. Filter by partner(s).
2. Retrieve approved updates by cycle or date.
3. Retrieve relevant `memory_chunks` by vector similarity if the question is semantic.
4. Use `partner_memory_summaries` as cached background context only.
5. Always cite/ground final output in Approved Updates.

### 15.4 Why Store `memory_text` If Update Text Already Exists?

This is a controlled derived copy.

Reason:

- Vector retrieval systems need chunk text next to embedding.
- It avoids repeated joins during retrieval.
- `update_id` unique FK keeps traceability.
- If approved update cannot change, memory text remains stable.

This is not uncontrolled repetition.

## 16. Agent Behavior

### 16.1 Agent Types

Agents:

1. Source extraction agent
2. Presenter analysis agent
3. Executive email agent
4. Report formatting/generation service
5. Memory embedding worker

### 16.2 Source Extraction Agent

Input:

- normalized source event
- connected source metadata
- developer-owned source rulebook
- allowed raw payload if source policy allows it

Output:

- zero, one, or many candidate Pending Updates

Rules:

- Do not create update for every source event.
- Use rulebook to decide meaningfulness.
- Output plain text only.
- One update comes from one source event/source URL.
- Same source URL plus same generated text is an exact duplicate.
- Same source URL plus different text is allowed.

Expected structured output:

```json
{
  "updates": [
    {
      "text": "Plain-text pending update.",
      "source_url": "https://...",
      "source_event_timestamp": "2026-08-07T10:30:00Z"
    }
  ]
}
```

### 16.3 Jira Agent

Reads:

- single issue events
- comments
- status/resolution changes
- due/target date changes
- priority/severity changes
- description/summary changes

Creates:

- Pending Updates when meaningful.

Stores:

- raw content behind scenes.

Shows:

- update text plus main Jira issue link.

### 16.4 Slack Agent

Reads:

- all channel messages
- all thread replies

Does not store:

- raw Slack message text

Stores:

- event IDs, timestamps, channel ID, sender hash

Creates:

- Pending Updates only when meaningful.

Shows:

- update text plus Slack channel link.

### 16.5 SharePoint Agent

Reads:

- single approved file source when file changes

Supports:

- DOCX
- PPTX
- XLSX
- PDF

Stores:

- copy of file in S3

Creates:

- Pending Updates according to document rulebook.

### 16.6 Confluence Agent

Reads:

- single page changes through integration/MCP

Stores:

- raw page content behind scenes

Creates:

- Pending Updates when meaningful.

### 16.7 GitHub Agent

Reads:

- repo meaningful events
- issue events
- PR events

Repo source can consider:

- issues
- PRs
- releases/tags
- commits
- security/advisories

Issue/PR source tracks:

- only the specific issue or PR

Stores:

- relevant raw event/content behind scenes.

### 16.8 Presenter Analysis Agent

Inputs:

- selected partners
- selected cycle
- Approved Updates only

Outputs:

- Executive Summary
- Decision Board

Rules:

- Do not use Pending Updates.
- Do not use Partner Metadata.
- Do not expose raw source content.
- Regenerate every Presenter View page load for v1.

### 16.9 Executive Email Agent

Inputs:

- cycle
- all Approved Updates for the cycle across all partners
- developer-owned email rulebook

Output:

- executive email draft artifact

Rules:

- No Partner Metadata.
- No Pending Updates.
- Same approved input as Word report.

## 17. Worker And Queue Design

### 17.1 Queues

Recommended queues:

```text
source-events-queue
source-events-dlq

report-generation-queue
report-generation-dlq

memory-queue
memory-dlq
```

### 17.2 Webhook Flow

1. Webhook endpoint verifies signature.
2. Endpoint resolves connected source.
3. Endpoint writes `source_events`.
4. Endpoint writes allowed `source_payloads`.
5. Endpoint enqueues source event job.
6. Endpoint returns quickly.

### 17.3 Source Worker Flow

1. Receive source event job.
2. Load `source_events` and source details.
3. Load allowed payload.
4. Run source extraction agent.
5. For each generated update:
   - compute text hash
   - check exact duplicate
   - insert `updates` row with `status = pending`
6. Mark event succeeded/failed.
7. Failed jobs retry through SQS policy.
8. Repeated failures move to DLQ.

### 17.4 Approval Flow

1. Contributor approves Pending Update.
2. Server verifies contributor owns partner.
3. Server updates `updates.status = approved`.
4. Server sets `approved_by`, `approved_at`.
5. Server creates memory job.
6. Server creates report generation jobs for that update cycle.
7. Response returns to contributor.

### 17.5 Report Regeneration Flow

1. Worker receives report generation job.
2. Loads approved updates for cycle.
3. Generates Word report and/or executive email.
4. Stores artifact in S3.
5. Upserts `report_artifacts`.
6. Logs `report_generation_runs`.
7. Retry silently on failure.

## 18. Security And Authorization Rules

### 18.1 Contributor Authorization

Contributor can act only when:

- user has contributor role
- user is assigned to partner

Applies to:

- metadata save
- pending update approve/edit/reject
- resource link changes
- connected source request/pause/resume

### 18.2 Presenter Authorization

Presenter can act only when:

- user has presenter role

Presenter can:

- read all partner metadata
- read all approved updates
- generate reports
- generate analysis

Presenter cannot mutate source data.

### 18.3 Admin Authorization

Admin can:

- manage users
- manage partners
- configure integrations
- approve/reject connected sources

Admin cannot:

- approve partner Pending Updates
- edit partner metadata
- edit developer-owned rulebooks

### 18.4 Source Permissions

The app must not become a permission bypass.

For SharePoint stored file copies:

- In-app view/download depends on original SharePoint permission.

For external links:

- User opens source in external tool.
- External tool permission controls access.

## 19. Deployment Components

Target AWS components:

```text
ECS Fargate service: web
ECS Fargate service: worker
Application Load Balancer
RDS/Aurora PostgreSQL
S3 private bucket
SQS queues and DLQs
Secrets Manager
CloudWatch Logs
```

### 19.1 Web Service

Runs:

- FastAPI API

Handles:

- JSON API
- Auth/session
- webhooks
- authorization

Does not handle:

- long AI processing
- report generation
- document parsing

### 19.2 Worker Service

Runs:

- source event workers
- report generation workers
- memory workers

Handles:

- source processing
- AI extraction
- report generation
- embeddings

### 19.3 Database

Use:

- RDS PostgreSQL or Aurora PostgreSQL

Needs:

- migrations
- automated backups
- encryption at rest
- private networking

### 19.4 Secrets

Use:

- Secrets Manager

Secrets:

- default login password hash or secret
- integration encryption master key
- Slack credentials
- Jira credentials
- SharePoint credentials
- Confluence credentials
- GitHub credentials
- OpenAI/Azure OpenAI credentials
- database credentials

## 20. Migration From Current Prototype

Do not rewrite everything at once.

Recommended sequence:

1. Freeze PRD and terminology.
2. Create target database schema in Alembic.
3. Create API module boundaries.
4. Move current route logic into domain routers/services.
5. Introduce PostgreSQL repository layer.
6. Introduce S3 storage abstraction.
7. Introduce worker process and queues.
8. Move source processing out of web request path.
9. Build or migrate frontend to Next.js.

If time is short:

- Keep current UI temporarily.
- Still use the target database model and service boundaries.
- Do not let the old giant route file remain the long-term shape.

## 21. Open Technical Decisions

1. Next.js now or later
   - Architecturally recommended.
   - If 4-5 day turnaround is strict, modularize backend first and keep current UI temporarily.

2. RDS PostgreSQL vs Aurora PostgreSQL
   - RDS PostgreSQL is simpler and enough for first production version.
   - Aurora is stronger for HA/scale, but more operationally involved.

3. Vector model and dimensions
   - Choose embedding model before finalizing `vector(n)` dimension.

4. Raw payload encryption
   - Decide whether database-level encryption is enough or raw payload text should be application-encrypted before storage.

5. Report generation sync vs worker-only
   - PRD wants immediate regeneration on approval.
   - Implementation should enqueue immediately, not block approval on document generation.

## 22. The Core Design In One Sentence

Build a modular product with Next.js client, FastAPI API, PostgreSQL source of
truth, S3 artifacts, SQS workers, developer-owned agent rulebooks, and a
normalized data model where Approved Updates are the official intelligence layer.
