# Current Project Reuse Assessment

## 1. Purpose

This document audits the existing `PartnerUpdateAutomation` project as input to the fresh product-shaped rebuild.

The goal is not to criticize the prototype for being a prototype. The goal is to decide, with solution-architect discipline, what should be reused, what should be adapted, and what should be rewritten so the new system has a clear client side, server side, database model, integration model, and deployment story.

No secret values were inspected or copied into this document. Only environment variable names, code structure, schema shape, and behavior were reviewed.

## 2. Executive Verdict

The existing project contains a lot of valuable implementation material, especially around:

- Slack, Jira, GitHub, and Microsoft 365 integration mechanics.
- Webhook signature verification and durable event queue concepts.
- Jira issue URL parsing, single-issue fetch, event normalization, REST/MCP switching.
- Microsoft Graph shared-link resolution and file download.
- DOCX/PPTX parsing, rich text/link preservation, and report/email generation.
- Current UI flows for contributor review, metadata, admin team/partners/integrations, and presenter intelligence.

But the current project shape should not be carried into the new stack as-is.

The current app is a successful prototype that has grown into a tightly coupled monolith:

- `dashboard/main.py` is about 12.8k lines and mixes routes, forms, integration admin, AI prompts, parsing orchestration, attachments, auth flows, report generation, and UI context building.
- `core/database.py` is about 6.1k lines and mixes schema creation, migrations, repository methods, seed data, ingestion lifecycle, metadata, memory, documents, and admin operations.
- The UI is mainly large Jinja templates, including `home.html` around 5.9k lines and `intelligence.html` around 5.2k lines.
- SQLite is used for the live app state, with in-code schema evolution rather than explicit migration files.
- Multiple older concepts still exist: workstreams, training sources, pending queues, staged updates, polling fallbacks, historical parser tables, assistant instruction UI, and source mappings that no longer match the latest PRD.

Recommendation:

- Reuse proven domain logic and connector internals.
- Use the current UI as a reference for product flows and styling.
- Rebuild the application structure, API surface, database schema, and integration workflows cleanly.

## 3. Current Inventory

### 3.1 Major Runtime Shape

Current app:

- FastAPI app with server-rendered Jinja templates.
- SQLite database at `db/arm_automation.db`.
- Python agents under `agents/`.
- Local output and attachment storage.
- Optional in-process schedulers and pollers.
- Environment variables plus an encrypted `integration_secrets` table for some admin-entered credentials.

Current important files:

| Area | Current files | Reuse stance |
|---|---|---|
| App/router layer | `dashboard/main.py` | Rewrite |
| DB/repository layer | `core/database.py` | Rewrite as Alembic + SQLAlchemy repositories |
| Contributor UI | `dashboard/templates/home.html` | Use as UI reference, not as-is |
| Presenter UI | `dashboard/templates/intelligence.html` | Use as UI reference, not as-is |
| Admin UI | `dashboard/templates/admin.html`, `admin_integrations.html`, `admin_train.html` | Use as UI reference selectively |
| Slack events | `agents/agent_1a/slack_events.py` | Adapt strongly |
| Slack polling | `agents/agent_1a/slack_poller.py` | Do not carry forward except token helper ideas |
| Jira events/fetching | `agents/agent_1b/jira_events.py`, `agents/agent_1b/agent.py` | Adapt strongly |
| Microsoft 365 files | `agents/agent_1e/agent.py` | Adapt internals, rewrite workflow |
| GitHub integration | `agents/agent_1f/agent.py` | Adapt internals, rewrite workflow |
| Ingestion pipeline | `agents/ingestion/pipeline.py` | Adapt concept, rewrite around new update lifecycle |
| Report writer | `agents/agent_4a/doc_writer.py` | Adapt |
| Email drafter | `agents/agent_6a/agent.py`, `skills.md` | Adapt strongly |
| Parsers | `core/doc_parser.py`, `core/ppt_parser.py`, `core/xlsx_parser.py`, `core/rich_text.py` | Mostly reusable |
| Auth helpers | `auth/auth.py`, `auth/passwords.py`, `auth/session.py` | Adapt |
| Secret encryption | `core/integration_secrets.py` | Reuse concept, adapt to Secrets Manager/Postgres |
| Attachment storage | `core/attachment_storage.py` | Reuse interface idea, replace local implementation with S3 |

### 3.2 Current Database Tables

The current SQLite database has these tables:

- `admin_partners`
- `assistant_instructions`
- `assistant_runs`
- `attachments`
- `doc_cycles`
- `document_chunks`
- `document_drafts`
- `document_links`
- `document_outline_nodes`
- `feedback_signals`
- `historical_updates`
- `ingestion_runs`
- `integration_event_queue`
- `integration_secrets`
- `knowledge_entities`
- `knowledge_entity_memory`
- `knowledge_upload_candidates`
- `knowledge_upload_sessions`
- `partner_memory`
- `partner_metadata_snapshots`
- `partner_resources`
- `password_reset_tokens`
- `pending_queue`
- `source_connections`
- `source_documents`
- `source_items`
- `source_mappings`
- `staged_updates`
- `sync_runs`
- `training_sources`
- `training_suggestions`
- `updates`
- `user_partner_assignments`
- `users`
- `workstream_context`
- `workstreams`

Current populated counts from local SQLite at the time of audit:

| Table | Rows |
|---|---:|
| `users` | 11 |
| `admin_partners` | 30 |
| `user_partner_assignments` | 47 |
| `partner_metadata_snapshots` | 3 |
| `partner_resources` | 4 |
| `source_connections` | 13 |
| `source_mappings` | 19 |
| `source_items` | 736 |
| `staged_updates` | 208 |
| `updates` | 600 |
| `integration_event_queue` | 4 |
| `document_drafts` | 17 |
| `partner_memory` | 29 |

These counts matter because they show the prototype already has real product concepts and testable data, not just scaffolding. But the table design is not the target schema.

## 4. Environment Variable Audit

### 4.1 Runtime Vars To Keep As Environment/Deployment Config

These belong in environment variables or AWS-managed secrets/config because they affect the runtime itself:

- `APP_ENV`
- `APP_BASE_URL`
- `APP_SECRET_KEY`
- `AUTH_MODE`
- `DATABASE_URL`
- `PORT`
- `INSTANCE_ID`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_KEY`
- `AZURE_OPENAI_API_VERSION`
- `OPENAI_CA_BUNDLE`
- `SSL_CERT_FILE`
- `MODEL_COMPLEX`
- `MODEL_FAST`
- `MODEL_EMBEDDING`
- `MODEL_WHISPER`
- `MODEL_TTS`
- `INTEGRATION_SECRETS_MASTER_KEY`
- `ATTACHMENT_MAX_BYTES`

New-stack placement:

- Local/dev: `.env`.
- AWS: ECS task env plus Secrets Manager/SSM Parameter Store.
- Database: do not store runtime secrets as visible rows.

### 4.2 Global Integration Secrets To Move To Admin-Managed Integration Config

These are global integration credentials. They should not be contributor-editable:

- Slack: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`
- Jira: `JIRA_BASE_URL`, `JIRA_PAT`, `JIRA_WEBHOOK_SECRET`, `JIRA_FETCH_BACKEND`
- Microsoft Graph/SharePoint: `MSGRAPH_TENANT_ID`, `MSGRAPH_CLIENT_ID`, `MSGRAPH_CLIENT_SECRET`, `MSGRAPH_M365_FILES_REDIRECT_URI`
- GitHub: `GITHUB_TOKEN`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_PRIVATE_KEY_PATH`, `GITHUB_APP_INSTALLATION_ID`

New-stack placement:

- `integrations` table stores non-secret metadata and enabled/disabled/test status.
- `integration_secrets` or AWS Secrets Manager stores secret material.
- Admin UI can save/test/disable these integrations.
- Secret values are never displayed after save.

### 4.3 Contributor-Specific Config To Move Out Of Env Vars

These should not live in environment variables:

- `SLACK_CHANNEL_UBER`
- Any `SLACK_CHANNEL_*`
- Jira issue URLs
- SharePoint file URLs
- Confluence page URLs
- GitHub repo/issue/PR URLs
- Partner-specific source mappings

New-stack placement:

- `connected_sources` plus type-specific child tables:
  - `connected_source_slack_channels`
  - `connected_source_jira_issues`
  - `connected_source_sharepoint_files`
  - `connected_source_confluence_pages`
  - `connected_source_github_targets`

Contributor can create/request/update/archive these through Connected Sources. Admin approves and tests.

### 4.4 Vars To Drop Or Deprioritize

The latest PRD says no polling fallback for webhook-capable integrations. These should not drive the new architecture:

- `SLACK_POLL_INTERVAL_MINUTES`
- `SLACK_POLL_INTERVAL_HOURS`
- `SLACK_LOOKBACK_HOURS`
- `JIRA_POLL_INTERVAL_HOURS`
- `JIRA_LOOKBACK_DAYS`
- `JIRA_INITIAL_LOOKBACK_MONTHS`
- `JIRA_MAX_RESULTS`
- `JIRA_BACKFILL_ENABLED`
- `M365_FILES_POLLING_ENABLED`
- `M365_FILES_POLL_INTERVAL_HOURS`
- `SHARED_MAILBOX_POLLING_ENABLED`
- `SHARED_MAILBOX_POLL_INTERVAL_MINUTES`
- `RUN_SCHEDULER`

Some scheduled jobs may still exist in the new stack, but they should be explicit background workers for report generation, retries, and maintenance, not primary ingestion for Slack/Jira/GitHub.

## 5. Reuse Classification

### 5.1 Copy Or Port Mostly

These are strong candidates for direct porting with cleanup:

#### Rich Text And Link Sanitization

Current:

- `core/rich_text.py`

Why reusable:

- Provides controlled HTML sanitization.
- Keeps inline links while stripping unsafe markup.
- Useful for approved update rendering, email generation, and report evidence.

Required changes:

- Convert to a pure utility package under `server/app/core/rich_text.py`.
- Add tests around allowed/disallowed tags and URL schemes.

#### DOCX/PPTX/XLSX Parsing

Current:

- `core/doc_parser.py`
- `core/ppt_parser.py`
- `core/xlsx_parser.py`

Why reusable:

- Existing parsers understand business documents and preserve useful metadata.
- The SharePoint Connected Source flow needs file parsing.
- Knowledge upload and memory extraction can reuse parsing primitives.

Required changes:

- Move parser logic behind `DocumentParserService`.
- Add parser result contracts using Pydantic models.
- Keep source-file-specific heuristics as rulebook-driven modules, not route helpers.

#### Password Hashing

Current:

- `auth/passwords.py`

Why reusable:

- Uses PBKDF2 with per-password salt and constant-time compare.
- Good enough for the short pre-SSO pilot.

Required changes:

- Put password policy behind backend auth service.
- Store only password hashes.
- Support later SSO mode without changing role/permission model.

#### Integration Secret Encryption Concept

Current:

- `core/integration_secrets.py`

Why reusable:

- Separates stored ciphertext from runtime master key.
- Provides a clear abstraction for set/get/status/tested.

Required changes:

- Prefer AWS Secrets Manager for real deployments.
- If storing encrypted ciphertext in Postgres, use a KMS-backed master key.
- Never derive production secret keys from `APP_SECRET_KEY`.

#### Attachment Storage Interface Concept

Current:

- `core/attachment_storage.py`

Why reusable:

- Has a clean boundary between attachment metadata and byte storage.
- Validates filenames/extensions and prevents path traversal.

Required changes:

- Replace `LocalAttachmentStorage` with `S3AttachmentStorage`.
- Keep local adapter only for development.
- Store S3 bucket/key/content hash/size in database.

#### OpenAI/Azure OpenAI Client Factory

Current:

- `core/config.py`

Why reusable:

- Supports both direct OpenAI and Azure OpenAI-like deployments.
- Keeps model names centralized.
- Handles corporate certificate trust better than ad hoc clients.

Required changes:

- Move settings to typed `pydantic-settings`.
- Separate runtime config from product settings.
- Add model-purpose config, not just `fast` and `complex`.

### 5.2 Adapt Strongly

These contain reusable engineering but should not be copied as-is.

#### Slack Events

Current:

- `agents/agent_1a/slack_events.py`

Reusable:

- Slack signature verification.
- Event ID generation.
- Headers-safe storage.
- Durable queue shape.
- Message filtering.
- Queue worker/retry/dead-letter concept.

Must change:

- Remove env channel mapping fallback.
- Remove polling as first-class path.
- Map channel ID through approved `connected_sources`.
- Include thread replies according to PRD.
- Store raw Slack content only for technical processing if absolutely required, not for UI display.
- Produce `source_events` and `updates` in the new lifecycle, not `source_items` + `staged_updates`.

New shape:

```text
Slack webhook
  -> verify signing secret
  -> enqueue source_event
  -> resolve channel connected_source
  -> normalize message/thread event
  -> rulebook extraction
  -> create Pending Update
```

#### Jira Integration

Current:

- `agents/agent_1b/agent.py`
- `agents/agent_1b/jira_events.py`

Reusable:

- `parse_jira_issue_key`
- `cycle_from_jira_timestamp`
- Jira PAT auth headers
- Jira MCP backend switch
- `fetch_jira_issue`
- `jira_test_connection`
- `verify_jira_webhook`
- `jira_event_id`
- Jira issue/comment/changelog normalization

Must change:

- Remove board polling as the product path.
- Remove board discovery as core product scope.
- Remove customer-field/source-mapping matching as the main way to resolve partners.
- Use approved single Jira issue connected source.
- Treat each meaningful Jira issue/comment/status/date/priority event as one source event.
- Rulebook determines whether event becomes pending update.

New shape:

```text
Contributor requests Jira issue URL
  -> Admin approves/tests global Jira integration and issue access
  -> Jira webhook arrives
  -> fetch full issue
  -> normalize only events for approved issue source
  -> create one or more Pending Updates
```

#### Ingestion Pipeline

Current:

- `agents/ingestion/pipeline.py`

Reusable:

- Normalized connector item concept.
- Idempotency via source ID/content hash.
- Duplicate detection concept.
- Classifier interface.
- Sync run/audit count concept.

Must change:

- Replace legacy `SourceItem -> staged_updates -> updates` model with:
  - `source_events`
  - `source_payloads`
  - `updates` with `status = pending | approved | rejected`
  - `update_review_actions`
- Remove workstream-first assumptions.
- Remove duplicate suppression that is too aggressive. Per PRD, exact duplicates can be rejected instantly, but near duplicates should remain broad for contributor review.
- Make source event timestamp determine cycle for source-generated updates.

#### Microsoft 365 / SharePoint

Current:

- `agents/agent_1e/agent.py`

Reusable:

- Graph auth flow.
- MSAL token refresh.
- Shared link to drive item resolution.
- File metadata read.
- File download.
- File extension detection.
- Parser dispatch to DOCX/PPTX.

Must change:

- Current flow is admin-configured standard documents with polling.
- New flow is contributor-requested single SharePoint file Connected Source.
- Need support for DOCX, PPTX, XLSX, and PDF.
- Need a SharePoint/file rulebook to describe how to interpret the file.
- Need no visible raw source excerpt in contributor UI.
- Need resource link auto-creation for approved file source.

New shape:

```text
Contributor requests SharePoint file URL
  -> Admin approves/tests global Graph access and file access
  -> System resolves drive_id/item_id
  -> Change notification or approved refresh event
  -> download file copy to S3
  -> parse by type
  -> rulebook extraction
  -> Pending Updates
```

#### GitHub Integration

Current:

- `agents/agent_1f/agent.py`

Reusable:

- GitHub webhook signature verification.
- GitHub App JWT/installation-token support.
- REST client helpers.
- Repo/issue/comment/event normalization.
- Queue worker/retry/dead-letter concept.

Must change:

- Current flow is AWS-specific by default.
- New PRD requires generic contributor-requested GitHub repo/issue/PR URL.
- Do not auto-create AWS partner.
- Use connected source target to resolve partner.
- Prefer webhook event flow over poll.
- Support repo-level all meaningful events, issue-only events, or PR-only events depending on source URL type.

#### Report And Email Generation

Current:

- `agents/agent_4a/doc_writer.py`
- `agents/agent_6a/agent.py`
- `agents/agent_6a/skills.md`

Reusable:

- Word doc generation mechanics.
- Email drafting rulebook style.
- Evidence selection logic concepts.
- Fallback email generation.
- Link preservation.
- Downloadable artifact creation.

Must change:

- Inputs must be exactly approved updates plus partner metadata and selected partners/month.
- Word report should not rely on hardcoded partner order or old categories.
- Email should follow the new developer-owned rulebook, not the old CSP RAMP-only assumptions.
- Store generated artifacts in `report_artifacts`, backed by S3, not just local `outputs`.
- Latest artifact per month gets overwritten or superseded according to PRD.
- PowerPoint generation is out of v1 scope.

#### Auth

Current:

- `auth/auth.py`
- `auth/session.py`
- `auth/passwords.py`

Reusable:

- Role helper idea.
- Session abstraction idea.
- PBKDF2 hashing.
- SSO transition concept.

Must change:

- Remove signup and password-reset flows from v1 if admin-managed users/passwords are the chosen pilot path.
- Use role assignments rather than one `role_id` plus boolean flags.
- Enforce contributor partner ownership in backend policies.
- Clarify bootstrap admin source.

### 5.3 Rewrite

These should not be carried forward except as reference.

#### `dashboard/main.py`

Rewrite reason:

- Too many responsibilities in one file.
- Routes, services, form parsing, AI prompts, integration admin, DB access, and UI context are tightly mixed.
- High regression risk if edited continuously.

Target replacement:

```text
server/app/api/routes/
server/app/services/
server/app/repositories/
server/app/connectors/
server/app/agents/
server/app/schemas/
```

#### `core/database.py`

Rewrite reason:

- Schema creation and migrations are embedded in runtime helper code.
- SQLite-specific patterns are everywhere.
- Current tables include repeated and legacy concepts.

Target replacement:

- PostgreSQL.
- SQLAlchemy ORM models.
- Alembic migrations.
- Repository classes grouped by domain.

#### Current Update Lifecycle Tables

Rewrite:

- `pending_queue`
- `staged_updates`
- `updates`

Reason:

- The PRD now has a cleaner lifecycle: Pending Update -> contributor edits if desired -> Approved/Rejected.
- Intermediary edit version history is not needed.
- Approved updates should be immutable; correction is a new manual update.

Target:

- One `updates` table with `status`.
- `update_review_actions` for approval/rejection action audit.
- `source_events` and `source_payloads` for provenance.

#### Source Connections And Source Mappings

Rewrite:

- `source_connections`
- `source_mappings`

Reason:

- They mix global integration config, partner mapping, channel mapping, and workflow status.
- Contributor vs admin ownership is not clear enough.

Target:

- `integrations` for global integration state.
- `integration_secrets` for secret material/status.
- `connected_sources` for contributor-requested partner-specific sources.
- Type-specific child tables for source details.
- `connected_source_approval_actions`.

#### Workstreams And Training Sources

Rewrite/remove from v1:

- `workstreams`
- `workstream_context`
- `training_sources`
- `training_suggestions`

Reason:

- Current PRD does not make workstreams a primary contributor/presenter concept.
- Rulebooks are developer-owned for now.
- Contributor-selected "commit to training" in Resource Links was explicitly moved out of metadata and simplified into Connected Sources.

Target:

- Optional `tags` or hidden classification later.
- Developer-owned rulebooks in code, not admin UI for v1.

#### Polling And In-Process Schedulers

Rewrite/remove:

- Slack polling.
- Jira board polling.
- GitHub polling as primary path.
- Shared mailbox polling.
- In-process APScheduler as central orchestration.

Reason:

- User explicitly does not want polling fallback where webhook/integration events exist.
- EC2/ECS multi-instance deployments should not depend on each web worker running its own scheduler.

Target:

- Webhooks -> queue.
- Worker service consumes queue.
- Scheduled jobs only for retries, report regeneration, maintenance, and optional approved refreshes.

## 6. Current-To-Target Database Mapping

| Current table | Target table(s) | Recommendation |
|---|---|---|
| `users` | `users`, `user_roles`, `sessions` | Keep user data concept; normalize roles |
| `user_partner_assignments` | `partner_assignments` | Keep concept; enforce one owner per partner if required |
| `admin_partners` | `partners` | Keep concept; rename and normalize |
| `partner_metadata_snapshots` | `partner_metadata_snapshots`, `partner_goals`, `partner_risks` | Split JSON blobs into queryable tables |
| `partner_resources` | `resource_links` | Keep concept; remove training coupling |
| `source_connections` | `integrations` | Split global integration state from partner source requests |
| `integration_secrets` | `integration_secrets` or AWS Secrets Manager references | Keep concept; harden secret storage |
| `source_mappings` | `connected_sources` + type-specific tables | Rewrite around contributor requests and admin approval |
| `integration_event_queue` | SQS + `source_events`/`integration_event_attempts` | Keep queue idea, move queue to AWS |
| `source_items` | `source_events`, `source_payloads` | Keep normalized-source concept, rename and clarify |
| `staged_updates` | `updates(status='pending')` | Merge into unified update lifecycle |
| `pending_queue` | `updates(status='pending')` | Merge into unified update lifecycle |
| `updates` | `updates(status='approved')` | Keep approved-update concept; make lifecycle explicit |
| `sync_runs` | `integration_runs` | Keep audit/run counts |
| `ingestion_runs` | `agent_runs` / `integration_runs` | Merge by purpose |
| `attachments` | `attachments` | Keep concept; move bytes to S3 |
| `doc_cycles` | `report_artifacts` | Replace with artifact table |
| `document_drafts` | `report_artifacts`, `generation_runs` | Keep generated artifact metadata |
| `source_documents` | `source_payloads`, `documents` | Adapt for SharePoint/knowledge files |
| `document_chunks` | `memory_chunks`, `source_payload_chunks` | Reuse idea, redesign |
| `document_outline_nodes` | Optional document parse metadata | Backlog unless needed |
| `document_links` | `resource_links`, source payload links | Adapt |
| `partner_memory` | `partner_memory_summaries` | Keep concept, redesign |
| `knowledge_entities` | `memory_entities` | Optional later |
| `knowledge_entity_memory` | `memory_chunks` / `memory_entities` | Optional later |
| `knowledge_upload_sessions` | `knowledge_upload_sessions` | Keep if knowledge upload in v1 |
| `knowledge_upload_candidates` | `updates(status='pending')` or upload candidates | Adapt |
| `historical_updates` | migration/import staging only | Do not put in core v1 schema |
| `assistant_instructions` | developer-owned rulebooks | Remove UI table for v1 |
| `assistant_runs` | `agent_runs` | Keep run logging concept |
| `feedback_signals` | `agent_feedback` | Optional later |
| `password_reset_tokens` | remove for pilot | Not needed if admin-set shared/default password |

## 7. Current UI Reuse Assessment

### 7.1 Contributor View

Current useful pieces:

- Partner selector and partner cards.
- Pending/Approved update tabs.
- Source chips and source filters.
- Approval/rejection/edit interactions.
- Partner Metadata section.
- Risk/issues table UI.
- Resource Library table UI.
- Manual update add flow.
- Jira paste/manual fallback flow.
- Guided file upload flow.

What should change:

- Add `Connected Sources` as first-class contributor section.
- Remove or hide Workstream-centric navigation.
- Remove source excerpts from visible UI if the PRD says no excerpts.
- Keep source links.
- Resource Links should be title + URL + optional description. Current resource UI has category and featured flag; those can be removed unless we explicitly decide they are useful.
- Connected Source links that auto-create Resource Links should show disabled/archived state in Resource Links if the source is archived.

### 7.2 Presenter View

Current useful pieces:

- Global read-only software ecosystem intelligence shape.
- Month/range selector.
- Partner metadata side pane.
- Approved update list.
- AI/analysis area.
- Document preview/download mechanics.
- Executive email modal and download.
- Decision Board-like analysis/table pattern.

What should change:

- Presenter data must be approved updates + partner metadata only.
- Analysis should be separate from raw Partner Metadata and Approved Updates.
- Default to all partners and current calendar month.
- No report editing for v1.
- Word report and email draft should be downloadable.
- PowerPoint generation should be removed/hidden for now.

### 7.3 Admin View

Current useful pieces:

- Admin console module layout.
- Partners administration.
- Team administration.
- Integration admin pages.
- Secret save/test concept.
- Last admin lock concept.

What should change:

- Admin should be a real control plane:
  - Users
  - Roles
  - Partner assignment
  - Global integrations
  - Connected Source approvals
  - Integration health
  - Audit logs
- Remove admin-owned workstreams as a core v1 surface.
- Remove admin rulebook/assistant instruction UI for v1 because rulebooks are developer-owned.
- Add approvals queue for contributor Connected Source requests.

## 8. Integration-Specific Reuse Decisions

### 8.1 Slack

Decision: adapt strongly.

Use:

- `verify_slack_signature`
- `slack_event_id`
- Slack event queue pattern
- supported message filtering
- message normalization concept

Do not use:

- `SLOT_CHANNEL_MAP`
- `SLACK_CHANNEL_*` partner mappings in env
- Slack polling as core path
- workstream hints as required source mapping

Needed new work:

- Connected Source request form: channel name, channel ID, bot invited confirmation checkbox.
- Admin approval/test flow.
- Channel-to-partner uniqueness rule.
- Thread reply handling.
- Rulebook-driven extraction.
- No raw Slack text in UI.

### 8.2 Jira

Decision: adapt strongly.

Use:

- `parse_jira_issue_key`
- `fetch_jira_issue`
- Jira REST/MCP switch
- `jira_test_connection`
- `verify_jira_webhook`
- `normalize_jira_issue_events`
- comment/changelog field filtering ideas

Do not use:

- Board polling as the product path.
- Board discovery as required flow.
- Customer-field partner detection as main product mapping.
- Workstream hints as required.

Needed new work:

- Contributor connected source for a single Jira issue URL.
- Admin approval and issue access test.
- Webhook event matching to approved issue sources.
- One source event can yield zero, one, or multiple pending updates.
- Multiple events from one issue can become multiple updates.

### 8.3 SharePoint / Microsoft 365 Files

Decision: reuse internals, rewrite workflow.

Use:

- MSAL auth.
- Graph token refresh.
- shared-link resolver.
- drive item metadata.
- file download.
- parser dispatch.

Do not use:

- Admin-configured standard document list as the main product flow.
- Polling as the primary processing path.
- Current partner fuzzy matching as the main source mapping.

Needed new work:

- Single-file Connected Source.
- File types: DOCX, PPTX, XLSX, PDF.
- Store downloaded file copy in S3.
- Rulebook per document/source style.
- Auto-create Resource Link after source approval.
- Surface no raw source excerpt.

### 8.4 Confluence

Decision: new integration.

Existing project does not appear to have a dedicated Confluence connector equivalent to Slack/Jira/GitHub/M365.

Can reuse:

- Jira/MCP pattern.
- generic connector interface.
- source event/update lifecycle.
- HTML/rich text sanitization utilities.

Needed new work:

- Contributor source request for single Confluence page URL.
- Admin/global config.
- MCP or REST-backed page fetch.
- Page update webhook if available.
- Rulebook extraction.
- Auto-create Resource Link.

### 8.5 GitHub

Decision: adapt strongly.

Use:

- webhook signature verification.
- GitHub App auth/JWT installation token logic.
- REST helper pagination.
- issue/comment/event normalization.
- queue worker concept.

Do not use:

- AWS-specific owner/repo defaults as core architecture.
- Auto-create AWS partner behavior.
- Polling as primary path.

Needed new work:

- Contributor source URL can be repo, issue, or PR.
- Admin approval/test validates app/token access.
- Repo-level source processes meaningful repo events.
- Issue/PR-level source processes only that object.
- Auto-create Resource Link for non-Slack GitHub source.

### 8.6 Knowledge Upload / Direct File Upload

Decision: adapt selectively.

Use:

- Parser and candidate extraction ideas.
- Guided upload UI ideas.
- Duplicate detection concept.
- Document chunking/memory concepts.

Do not use:

- Current workstream/training-source-heavy model.
- Admin rulebook UI.
- Large route-local helper functions in `dashboard/main.py`.

Needed new work:

- Decide whether knowledge upload is Admin-only v1 or Contributor upload v1.
- Align with PRD: admin knowledge upload can feed future update extraction/memory, but contributor metadata remains manually filled.
- Store memory as structured source payloads/chunks in Postgres/S3.

## 9. Backend Build Implications

The fresh backend should be built as modules, not as one large route file.

Recommended target modules:

```text
server/app/
  main.py
  core/
    config.py
    security.py
    time.py
    logging.py
  db/
    base.py
    session.py
    models/
    migrations/
  api/
    routes/
      auth.py
      users.py
      partners.py
      metadata.py
      resource_links.py
      connected_sources.py
      updates.py
      presenter.py
      reports.py
      admin_integrations.py
      webhooks.py
  services/
    auth_service.py
    partner_service.py
    metadata_service.py
    connected_source_service.py
    update_service.py
    approval_service.py
    report_service.py
    analysis_service.py
  connectors/
    slack/
    jira/
    sharepoint/
    confluence/
    github/
  agents/
    rulebooks/
    extraction_agent.py
    presenter_analysis_agent.py
    email_agent.py
  workers/
    source_event_worker.py
    report_worker.py
  storage/
    s3.py
    local.py
  parsers/
    docx.py
    pptx.py
    xlsx.py
    pdf.py
```

The new backend should preserve the product learnings from the prototype but not the prototype coupling.

## 10. Client Build Implications

If the new client uses Next.js/React:

- Use current templates as UI reference.
- Rebuild screens as components.
- Do not port the full Jinja templates.
- Keep copy, layout intent, table shape, and key interaction patterns.
- Replace server-rendered form posts with typed API calls.

Recommended client modules:

```text
client/src/
  app/
    login/
    contributor/
    presenter/
    admin/
  components/
    layout/
    partners/
    metadata/
    updates/
    connected-sources/
    resource-links/
    integrations/
    reports/
    analysis/
    ui/
  lib/
    api.ts
    auth.ts
    dates.ts
    validators.ts
  types/
```

UI surfaces to preserve visually:

- Contributor table layout for Pending and Approved Updates.
- Partner Metadata structure.
- Key Risks & Issues table.
- Resource Links table, simplified.
- Presenter intelligence layout.
- Admin console module layout.
- Admin integrations cards/statuses.

UI surfaces to modify:

- Add Contributor `Connected Sources`.
- Remove PowerPoint generation from v1.
- Remove visible source excerpts where PRD says none.
- Replace workstream tabs with partner/cycle/source filters.
- Move source configuration out of Add Update and into Connected Sources.

## 11. What Can Be Migrated As Data

Potentially migrate:

- Users, after role normalization.
- Partners.
- Contributor-partner assignments.
- Current partner metadata snapshots if still relevant.
- Current partner resource links after simplifying fields.
- Approved updates, if they represent real historical evidence.
- Integration global config names/statuses, not secret values unless intentionally re-entered.
- Parser-derived historical knowledge only if the product team wants existing memory in v1.

Do not blindly migrate:

- Pending/staged updates.
- Source mappings.
- Workstreams.
- Training sources.
- Assistant instructions.
- Sync run history.
- Local output file paths.
- Poller cursor state.

## 12. Product Decisions Confirmed By This Audit

The code audit does not change the major PRD direction. It strengthens it.

Confirmed:

- FastAPI can still be a strong backend choice if it is rebuilt cleanly.
- PostgreSQL is the right DB starting point.
- The current integration modules reduce implementation risk.
- The current UI gives us strong reference material.
- A fresh folder/rebuild is justified because current coupling is too high.
- The new architecture should split admin global integration config from contributor Connected Sources.
- Webhooks/events should be primary for Slack/Jira/GitHub.
- Source-generated updates should enter review first, not become official immediately.
- Approved Updates should be the clean source of truth for presenter outputs.

## 13. Recommended Reuse Priority

Priority 1, bring forward early:

- Auth password hash helper.
- Runtime config patterns.
- Integration secret abstraction.
- Slack signature verification.
- Jira URL parsing/fetch/test/webhook verification/event normalization.
- Resource Link and Partner Metadata data concepts.
- Current contributor/presenter/admin UI references.

Priority 2, bring forward during integrations:

- Microsoft Graph shared-link resolver/download.
- GitHub App/webhook/auth helpers.
- Ingestion idempotency and duplicate strategy.
- Parser utilities.
- Rich text/link preservation.

Priority 3, bring forward after core lifecycle:

- Word report generator.
- Executive email rulebook and generation logic.
- Partner memory/chunking ideas.
- Knowledge upload candidate extraction.

Avoid carrying forward:

- Giant route/database files.
- SQLite runtime schema management.
- Env-based partner/channel mappings.
- Polling-first ingestion.
- Workstream-first UX/data model.
- Admin-editable rulebooks for v1.
- PowerPoint generation in v1.

## 14. Short Answer For The Technical DevOps Conversation

If someone asks, "Can your current project be containerized and deployed to EC2?"

Answer:

Yes, the current project can be containerized, and much of the integration logic is usable. But the current structure is prototype-shaped: SQLite, local file outputs, in-process schedulers, giant route/database modules, and mixed UI/server/business logic. For the production-shaped rebuild, we are moving to a clearer architecture: React/Next.js client, FastAPI backend, PostgreSQL, S3-backed storage, queue-based webhook workers, admin-managed global integration credentials, contributor-managed Connected Sources, and a normalized update lifecycle.

If someone asks, "What will you reuse?"

Answer:

We will reuse proven connector internals, parsers, rulebooks, document/email generation logic, rich text handling, and UI reference flows. We will not reuse the monolithic app shape, SQLite schema, polling fallbacks, or workstream-heavy data model.

If someone asks, "What is the key architectural improvement?"

Answer:

The key improvement is separating concerns:

- Client views are separate from backend APIs.
- Global integration credentials are separate from contributor source configuration.
- Source events are separate from reviewed business updates.
- Pending updates and approved updates share one clear lifecycle.
- Reports and presenter intelligence read only approved updates and partner metadata.
- Workers handle integrations and generation outside the web request path.
