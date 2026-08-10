# Sequential Feature Build Plan

## 1. Purpose

This document converts the PRD, solution architecture, current-project audit, and UI workshop decisions into a sequential feature build plan for the fresh product-shaped rebuild.

The plan is intentionally feature-based rather than screen-based. Each feature contains:

- Backend scope.
- Client/UI scope.
- Reuse decision from the current project.
- Acceptance criteria.
- Notes about what is intentionally not being built yet.

The target stack remains:

- Client: Next.js / React / TypeScript.
- Server: FastAPI / Python.
- Database: PostgreSQL with Alembic migrations.
- Storage: S3-compatible artifact/file storage.
- Background work: queue/worker model.

## 2. UI Decisions To Carry Into Features

Locked UI decisions:

- Login: keep current design, local password login, remove Forgot Password and Create Account.
- Landing page: keep as-is for now.
- Account role switcher: show only available views.
- Partner selection: keep as-is.
- Contributor Pending Updates: keep as-is, add Connected Sources tab later.
- Contributor Approved Updates: keep exactly as-is.
- Contributor Partner Metadata: keep all current sections.
- Resource Library: simplify to Title + URL + optional Description.
- Contributor Connected Sources: new design pending from user/Figma.
- Presenter feed: keep as-is, remove Export Deck.
- Presenter metadata: show only for single partner.
- Executive Summary: no change for now.
- Decision Board / Analysis View: keep as-is.
- Draft Email: keep as-is.
- Admin Team / Users / Roles: keep current Team UI; no password UI.
- Admin Partners / Assignments: keep as-is.
- Admin Global Integrations: new design pending from user/Figma.
- Admin Connected Source Approvals: new design pending from user/Figma.
- Admin Health / Audit: backlog.
- Reports / Word Download: backlog.
- Manual Add Update: keep as-is.
- File / Knowledge Upload: keep as-is.

## 3. Feature Sequence

### Feature 01 - Fresh Project Foundation

#### Goal

Create the new folder/project structure and establish the client/server/database foundation.

#### Backend Scope

- Create server app structure.
- Add FastAPI app bootstrap.
- Add typed settings.
- Add PostgreSQL connection.
- Add Alembic migrations.
- Add health endpoint.
- Add structured logging.

#### Client/UI Scope

- Create Next.js app.
- Establish base layout primitives.
- Establish color/token baseline from current UI:
  - dark navy top bar
  - teal primary actions
  - light gray workspace
  - compact table/card styling
- No full business screen yet.

#### Reuse From Current Project

- Reuse current visual direction.
- Reuse `core/config.py` ideas, but rewrite as typed settings.

#### Acceptance Criteria

- Fresh app runs locally.
- Server health check works.
- Client shell loads.
- PostgreSQL migration system works.

---

### Feature 02 - Auth, Sessions, And Local Login

#### Goal

Implement pre-SSO local login with role-aware session behavior.

#### Backend Scope

- User table.
- Password hash storage.
- Session handling.
- Login/logout endpoints.
- Local password handled at code/config level for now.
- Prepare clean extension point for future ARM SSO.

#### Client/UI Scope

- Reuse current login page design.
- Keep:
  - username/email field
  - password field
  - show password
  - keep me signed in
  - sign in button
  - internal-access-only note
- Remove:
  - Forgot Password
  - Create a new one
- Landing page remains as-is for now.

#### Reuse From Current Project

- Reuse `auth/passwords.py` logic.
- Reuse current login visual layout.
- Reuse current landing page as visual reference.

#### Acceptance Criteria

- Admin/local users can login.
- Unauthorized users see login.
- No signup UI.
- No forgot-password UI.
- Password values are never displayed in Admin.

---

### Feature 03 - Role Model And Account View Switcher

#### Goal

Support Contributor, Presenter, and Admin roles, including users with multiple roles.

#### Backend Scope

- Role assignment model.
- Role authorization policies.
- View resolution after login.
- Active view preference/session state.

#### Client/UI Scope

- Reuse top-right user-name dropdown pattern.
- Show only views the user has access to.
- Active view is checked/disabled.
- Contributor/Presenter switching works via account menu.
- Admin Console appears only for users with admin access.

#### Reuse From Current Project

- Reuse current account view switcher behavior and styling.

#### Acceptance Criteria

- Contributor-only users only see Contributor View.
- Presenter-only users only see Presenter View.
- Contributor+Presenter users can switch both ways.
- Admin is only visible to admins.

---

### Feature 04 - Admin Team / Users

#### Goal

Allow Admin to create and manage users and roles.

#### Backend Scope

- Create user.
- Edit user.
- Deactivate/reactivate user if retained.
- Assign roles.
- No invitation system for v1.
- No password UI.

#### Client/UI Scope

- Reuse current Team screen UI as-is as much as possible.
- Keep table/form layout.
- Keep add/edit member pattern.
- Keep name `Team` for now.
- Roles are Contributor / Presenter / Admin.
- No password set/reset fields.
- No invitation UI in final v1 behavior.

#### Reuse From Current Project

- Reuse current Admin Team layout.
- Reuse role checkbox visual pattern.

#### Acceptance Criteria

- Admin can create/edit user role assignment.
- Users with updated roles see correct views.
- Password setup is not exposed in UI.

---

### Feature 05 - Admin Partners And Assignments

#### Goal

Allow Admin to manage partner records and current assignment behavior.

#### Backend Scope

- Partner table.
- Partner create/edit/archive.
- Contributor partner assignment.
- Preserve current assignment behavior for now.

#### Client/UI Scope

- Keep current Partners screen as-is.
- Keep add/edit/archive UI.
- Keep current assignment behavior.
- No redesign for now.

#### Reuse From Current Project

- Reuse current Admin Partners screen.

#### Acceptance Criteria

- Admin can add/edit/archive partners.
- Partner assignments are respected by Contributor View.

---

### Feature 06 - Contributor Partner Selection

#### Goal

Let contributors with many partners choose which partner to work on.

#### Backend Scope

- API for contributor-assigned partners.
- Partner counts:
  - updates
  - integrations/connected source count
  - last activity

#### Client/UI Scope

- Keep Partner Selection screen as-is.
- Contributors with many partners land here.
- Contributors with one partner land directly in Contributor View.
- Keep search.
- Keep partner cards.

#### Reuse From Current Project

- Reuse current Partner Selection visual and behavior.

#### Acceptance Criteria

- Multi-partner contributor lands on selection screen.
- Single-partner contributor lands on partner dashboard.
- Search filters partner cards.

---

### Feature 07 - Contributor Dashboard Shell

#### Goal

Create the shared contributor layout that hosts metadata, pending updates, approved updates, and connected sources.

#### Backend Scope

- Dashboard context endpoint.
- Partner/cycle context.
- Last activity.
- Tab counts.

#### Client/UI Scope

- Reuse current Contributor View shell:
  - dark top bar
  - selected partner dropdown
  - account menu
  - partner name and last activity
  - search
  - month selector
  - `+ Add update`
  - tabs
- Final tabs:
  - Partner Metadata
  - Pending Updates
  - Approved Updates
  - Connected Sources
- Pending Updates remains default tab.

#### Reuse From Current Project

- Reuse current contributor shell/layout.

#### Acceptance Criteria

- Contributor dashboard loads for assigned partners only.
- Unassigned partner access is denied.
- Tab routing works.

---

### Feature 08 - Partner Metadata And Resource Library

#### Goal

Allow contributors to edit monthly partner metadata.

#### Backend Scope

- Partner metadata snapshot table.
- Store latest saved metadata for partner/month.
- No intermediary edit version history.
- Save triggered by Contributor clicking Save Metadata.
- Metadata includes all current sections:
  - Status
  - Why this partner
  - Business Priority
  - Highlights / Status
  - Goals
  - Execution Timeline
  - Key Risks & Issues
  - Resource Library

#### Client/UI Scope

- Reuse current Partner Metadata UI.
- Keep status Green / Amber / Red.
- Keep all current metadata sections.
- Keep add/remove rows.
- Keep Save Metadata button.
- Keep Key Risks & Issues table style.
- Modify Resource Library:
  - Title
  - URL
  - optional Description
- Remove Resource Library:
  - Category
  - Featured
- Resource Links remain inside Partner Metadata.

#### Reuse From Current Project

- Reuse metadata screen heavily.
- Modify Resource Library row only.

#### Acceptance Criteria

- Contributor can save metadata for assigned partner/month.
- Presenter can read metadata for single selected partner.
- Resource Links are partner-level and always visible.

---

### Feature 09 - Update Lifecycle: Pending And Approved Updates

#### Goal

Implement the core update lifecycle.

#### Backend Scope

- Unified `updates` table with statuses:
  - pending
  - approved
  - rejected
- Manual update creation enters pending.
- Source-generated update enters pending.
- Contributor can approve/edit/dismiss pending update.
- Approved updates are read-only.
- No approved update edit.
- No correction action for now.
- No intermediate edit history.

#### Client/UI Scope

- Pending Updates:
  - keep current UI as-is
  - keep source chips
  - keep search/filter/month
  - keep Approve/Edit/Dismiss
  - keep bulk actions for now
- Approved Updates:
  - keep exactly as-is
  - read-only
  - same row style
  - same source chip/source link behavior

#### Reuse From Current Project

- Reuse current Pending/Approved row UI.
- Rewrite backend lifecycle cleanly.

#### Acceptance Criteria

- Pending list shows current partner/month pending updates.
- Approve moves item to Approved.
- Dismiss removes from active pending list.
- Approved list is read-only.

---

### Feature 10 - Manual Add Update

#### Goal

Allow contributors to manually add an update.

#### Backend Scope

- Create manual pending update.
- Manual update has no source link.
- Approval date determines reporting cycle if needed by lifecycle.

#### Client/UI Scope

- Keep Manual Add Update visually as-is.
- Same `+ Add update` flow.
- Same manual form.
- Manual update appears in Pending Updates first.

#### Reuse From Current Project

- Reuse current manual add update UI.

#### Acceptance Criteria

- Contributor can create manual update.
- Manual update appears as pending.
- Manual update can be approved/dismissed like source-generated update.

---

### Feature 11 - File And Knowledge Upload

#### Goal

Preserve current file/knowledge upload capability for now.

#### Backend Scope

- Keep/upload file handling concept.
- Store uploaded file metadata.
- Parse supported files where existing behavior already supports it.
- Keep Admin Knowledge Upload path.

#### Client/UI Scope

- Keep current Contributor File Upload UI as-is.
- Keep current Admin Knowledge Upload UI as-is.
- No redesign for now.
- Do not resolve deeper source/training distinction yet.

#### Reuse From Current Project

- Reuse file upload UI.
- Reuse parser utilities where possible.

#### Acceptance Criteria

- Existing upload flow remains available in new app if included in v1.
- Upload UI matches current flow.

---

### Feature 12 - Contributor Connected Sources

#### Goal

Add the missing contributor tab where partner-specific source requests are created and managed.

#### Backend Scope

- `connected_sources` table.
- Type-specific details for:
  - Slack
  - Jira
  - SharePoint
  - Confluence
  - GitHub
- Contributor can request source.
- Contributor can see source status.
- Contributor can archive/pause/resubmit as rules allow.
- Admin approval required before Active.

#### Client/UI Scope

- New screen/tab required.
- User will provide Figma design.
- Must sit as fourth Contributor tab.
- Must not show global secrets.
- Must not show raw source excerpts.
- Must not mention polling.
- Source types:
  - Slack Channel
  - Jira Issue
  - SharePoint File
  - Confluence Page
  - GitHub Repo / Issue / PR
- Statuses:
  - Pending approval
  - Needs access setup
  - Active
  - Rejected
  - Disabled / Archived
  - Failed

#### Reuse From Current Project

- No exact screen exists.
- Reuse contributor shell/tab style.

#### Acceptance Criteria

- Contributor can request each source type.
- Requests appear with status.
- Existing connected sources are visible.
- Connected Sources does not overlap with Resource Links.

---

### Feature 13 - Admin Global Integrations

#### Goal

Allow Admin to configure app-level/global integration credentials and health.

#### Backend Scope

- `integrations` table.
- Secret storage abstraction.
- Save/test/enable/disable global integrations.
- Supported global integrations:
  - Slack
  - Jira
  - SharePoint / Microsoft Graph
  - Confluence
  - GitHub

#### Client/UI Scope

- New design required.
- User will provide Figma design.
- This replaces/adapts current Admin Integrations UI.
- Must separate global credentials from contributor source requests.
- Must not include:
  - Slack channel IDs
  - Jira issue URLs
  - SharePoint file URLs
  - GitHub repo/issue URLs
  - Confluence page URLs
  - polling settings
  - workstreams
  - rulebook editing
- Should show:
  - status
  - credentials configured/not configured
  - webhook URL/copy action
  - test connection
  - enabled/disabled
  - recent health summary

#### Reuse From Current Project

- Reuse admin visual tone.
- Reuse secret save/test concepts.
- Do not reuse current mapping-heavy integration UI as-is.

#### Acceptance Criteria

- Admin can configure/test each global integration.
- Contributor source approvals are blocked if global integration unavailable.

---

### Feature 14 - Admin Connected Source Approvals

#### Goal

Allow Admin to approve/reject contributor-requested connected sources.

#### Backend Scope

- Approval actions.
- Access test before activation.
- Rejection status.
- Needs access setup status.
- Duplicate detection:
  - exact duplicate can be rejected/flagged
  - near duplicates remain visible

#### Client/UI Scope

- New design required.
- User will provide Figma design.
- Must be an Admin approval workbench.
- Should include:
  - Needs Review queue
  - Active
  - Rejected
  - Failed / Attention
  - All
- Detail drawer for request review.
- Actions:
  - test access
  - approve and activate
  - reject
  - mark needs access setup
  - disable active source
- Must not include global secrets.

#### Reuse From Current Project

- Reuse admin table/drawer visual patterns where appropriate.
- No exact current screen exists.

#### Acceptance Criteria

- Pending connected source requests appear for Admin.
- Admin can approve only when global integration is available and access test passes.
- Contributor sees resulting status.

---

### Feature 15 - Source Event Queue And Worker Foundation

#### Goal

Create the source-event processing backbone.

#### Backend Scope

- Source event table.
- Source payload table.
- Queue worker.
- Idempotency key.
- Retry/dead-letter concept.
- Agent run logging.
- Exact duplicate handling.

#### Client/UI Scope

- No major end-user screen.
- Minimal status messages may appear in Connected Sources/Admin approvals.

#### Reuse From Current Project

- Reuse concepts from:
  - `integration_event_queue`
  - `agents/ingestion/pipeline.py`
  - sync run counts

#### Acceptance Criteria

- Webhook/source events can be queued and processed.
- Failures are recorded.
- Duplicate events do not create duplicate pending updates.

---

### Feature 16 - Slack Connected Source Processing

#### Goal

Support Slack channel connected sources.

#### Backend Scope

- Slack signing secret verification.
- Slack webhook endpoint.
- Channel-to-connected-source resolution.
- Process messages and thread replies.
- Rulebook extraction.
- No raw Slack text in UI.
- Slack does not create Resource Links.

#### Client/UI Scope

- Contributor Connected Sources Slack request state from Figma design.
- Admin approval drawer Slack state from Figma design.
- Admin Global Integrations Slack detail from Figma design.

#### Reuse From Current Project

- Reuse/adapt:
  - `verify_slack_signature`
  - Slack event ID
  - message filtering
  - queue worker concept
- Do not reuse polling/channel env mapping as product path.

#### Acceptance Criteria

- Slack events for active source can create Pending Updates.
- Contributor can review generated updates.

---

### Feature 17 - Jira Connected Source Processing

#### Goal

Support single Jira issue connected sources.

#### Backend Scope

- Jira global config.
- Jira webhook verification.
- Single issue URL parsing.
- Fetch issue via REST/MCP.
- Normalize issue/comment/status/date/priority events.
- Rulebook extraction.
- Source event cycle based on Jira event timestamp.
- Jira source can create Resource Link.

#### Client/UI Scope

- Contributor Jira source request form from Connected Sources design.
- Admin approval/access test UI.
- Resource Link auto-created for approved Jira source.

#### Reuse From Current Project

- Reuse/adapt:
  - `parse_jira_issue_key`
  - `fetch_jira_issue`
  - `jira_test_connection`
  - `verify_jira_webhook`
  - event normalization
  - MCP/REST switch
- Remove board polling from product path.

#### Acceptance Criteria

- Approved Jira issue source can generate Pending Updates from meaningful events.
- Contributor sees source link, not source excerpt.

---

### Feature 18 - SharePoint Connected Source Processing

#### Goal

Support single SharePoint file connected sources.

#### Backend Scope

- Microsoft Graph global config.
- File URL resolution.
- File access test.
- File copy storage.
- Parse DOCX/PPTX/XLSX/PDF.
- Rulebook extraction.
- SharePoint source can create Resource Link.

#### Client/UI Scope

- Contributor SharePoint source request form from Connected Sources design.
- Admin approval/access test UI.
- Resource Link auto-created for approved SharePoint source.

#### Reuse From Current Project

- Reuse/adapt:
  - Graph auth ideas
  - shared link resolver
  - file metadata/download
  - parser dispatch

#### Acceptance Criteria

- Approved single-file source can be tested and processed.
- File-derived Pending Updates appear for contributor review.

---

### Feature 19 - Confluence Connected Source Processing

#### Goal

Support single Confluence page connected sources.

#### Backend Scope

- Confluence global config.
- Page URL parsing.
- Page access test.
- Page fetch via REST/MCP-style connector.
- Rulebook extraction.
- Confluence source can create Resource Link.

#### Client/UI Scope

- Contributor Confluence source request form from Connected Sources design.
- Admin approval/access test UI.
- Resource Link auto-created for approved Confluence source.

#### Reuse From Current Project

- No dedicated current connector.
- Reuse Jira/MCP connector pattern.
- Reuse rich text sanitation concepts.

#### Acceptance Criteria

- Approved Confluence page source can generate Pending Updates when content changes/events arrive.

---

### Feature 20 - GitHub Connected Source Processing

#### Goal

Support GitHub repo/issue/PR connected sources.

#### Backend Scope

- GitHub global config.
- GitHub App/PAT auth.
- Webhook signature verification.
- Parse target URL:
  - repo
  - issue
  - PR
- Process meaningful events.
- GitHub source can create Resource Link.

#### Client/UI Scope

- Contributor GitHub source request form from Connected Sources design.
- Admin approval/access test UI.
- Resource Link auto-created for approved GitHub source.

#### Reuse From Current Project

- Reuse/adapt:
  - GitHub App JWT/install token
  - webhook verification
  - issue/comment/event normalization
- Remove AWS-specific assumptions from core product.

#### Acceptance Criteria

- Approved GitHub source can generate Pending Updates.
- Repo/issue/PR source scopes are respected.

---

### Feature 21 - Presenter Intelligence And Draft Email

#### Goal

Deliver the presenter read-only experience and email draft generation.

#### Backend Scope

- Read approved updates by month/partner scope.
- Read partner metadata for single selected partner.
- Decision Board/Analysis endpoint using existing analysis behavior.
- Draft email generation using developer-owned rulebook.
- No PowerPoint export.
- No Word report UI for now.

#### Client/UI Scope

- Presenter Feed:
  - keep current UI as-is
  - All Partners default
  - partner selector
  - month selector
  - search
  - Ask AI
  - Analysis view
  - Draft email
  - remove Export Deck
- Presenter Metadata:
  - show only when single partner selected
  - read-only
  - resource links clickable
- Executive Summary:
  - no UI change for now
  - covered by current Analysis/AI area for now
- Decision Board / Analysis View:
  - keep current Analysis View exactly as-is
- Draft Email:
  - keep as-is
  - no in-app editing required

#### Reuse From Current Project

- Reuse presenter feed UI.
- Reuse Analysis View UI.
- Reuse Draft Email modal.
- Reuse email rulebook concept.

#### Acceptance Criteria

- Presenter can view approved updates for all partners.
- Presenter can select one partner and see metadata.
- Presenter can use Analysis View.
- Presenter can draft email.
- Export Deck is not shown.

---

### Feature 22 - Enterprise AI Runtime Foundation

#### Goal

Add the production-shaped AI runtime foundation for the enterprise
OpenAI-compatible endpoint.

#### Backend Scope

- Add AI runtime settings.
- Add OpenAI-compatible client dependency.
- Add a single backend client factory under `app.agents.runtime`.
- Keep AI disabled by default in local development.
- Validate missing endpoint, key, and model configuration clearly when AI is
  enabled.

#### Client/UI Scope

- No UI.

#### Acceptance Criteria

- API and worker images include the AI runtime dependency.
- Local app starts with AI disabled.
- Enabled AI configuration fails fast if required settings are missing.
- Settings are ready for AWS Secrets Manager or SSM injection.

---

### Feature 23 - Developer-Owned Rulebook Framework

#### Goal

Create a versioned, packaged markdown rulebook framework for agent behavior.

#### Backend Scope

- Add a packaged rulebook directory.
- Add a registered rulebook manifest.
- Add rulebook loading, validation, hashing, and trace-version calculation.
- Keep rulebooks deployed through the backend image for API and worker.

#### Client/UI Scope

- No UI.
- Admin-editable rulebooks remain out of scope.

#### Acceptance Criteria

- Registered placeholder rulebooks load successfully.
- Invalid or unregistered rulebook names are rejected.
- Missing required sections are rejected.
- Rulebook content hash is available for future `agent_runs` tracing.

---

### Feature 23B - Rulebook Business Interview

#### Goal

Convert the first placeholder rulebook into an approved product decision pack
before implementation starts.

#### Backend Scope

- No runtime code.
- Choose the first rulebook to finalize.
- Capture event scope, extraction rules, ignore rules, language rules, output
  contract, dedupe behavior, traceability expectations, and golden examples.
- Document any required backend validation or agent-run audit behavior.

#### Client/UI Scope

- No immediate UI.
- Capture UI implications if the chosen rulebook requires contributor-visible
  confidence, attention, source, or reason indicators.

#### Reuse From Current Project

- Use the old project only for reference ideas.
- Do not copy old prompts without reviewing whether they match the new product
  model.

#### Acceptance Criteria

- First rulebook is selected.
- Product owner completes the one-question-at-a-time interview.
- Decision pack is documented and approved.
- No model-backed extraction starts until the decision pack is accepted.

---

### Feature 23C - First Production Rulebook Content

#### Goal

Replace one placeholder markdown rulebook with approved developer-owned
production content.

#### Backend Scope

- Update the chosen rulebook markdown file.
- Preserve the required rulebook metadata and section contract.
- Add or update tests if the contract changes.
- Keep the rulebook packaged into API and worker images.

#### Client/UI Scope

- Only implement UI changes if Feature 23B identified a required display change.

#### Acceptance Criteria

- The chosen rulebook no longer has placeholder content.
- Rulebook version is updated.
- Loader tests pass.
- The rulebook can be traced through `trace_version`.

---

### Feature 24A - Agent Extraction Infrastructure

#### Goal

Add shared source-event extraction infrastructure without activating
model-backed extraction.

#### Backend Scope

- Resolve source types to registered source-event rulebooks.
- Build a sanitized source-event input envelope.
- Reference retained payloads without copying raw payload content into model
  input.
- Add deterministic input fingerprinting.
- Add an infrastructure-only extraction orchestrator.
- Allow extraction output to update `agent_runs` rulebook/model metadata.

#### Client/UI Scope

- No UI.

#### Acceptance Criteria

- Supported source types resolve to the correct rulebook.
- Unsupported source types fail clearly.
- Default worker processing uses the extraction infrastructure but creates no
  pending updates.
- Existing source-specific deterministic webhook processors are not replaced.

---

### Feature 24B - Model Output Contract And Validation

#### Goal

Define strict model-output schemas and validation before any model-generated
draft update can be created.

#### Backend Scope

- Add Pydantic validation models for source-event extraction output.
- Validate create-vs-ignore decisions.
- Validate draft update title, summary, source metadata, confidence, and review
  flags.
- Add safe failure behavior for malformed model output.
- Do not call the model yet unless using a controlled test adapter.

#### Client/UI Scope

- No UI unless Feature 23B identifies required contributor-visible flags.

#### Acceptance Criteria

- Invalid model-like output cannot create pending updates.
- Valid ignored output records an agent run but creates no update.
- Valid draft output can be converted into an internal pending-update command in
  tests.
- Unknown model output fields fail validation.
- Confidence, event importance, source URL, title, and summary are validated
  before any future database write.

---

### Feature 24C - Model Adapter And Dry-Run Extraction

Status: implemented locally.

#### Goal

Add a model adapter and dry-run execution path without creating draft updates
from model output yet.

#### Backend Scope

- Add an extraction model adapter using the Feature 22 AI runtime.
- Build request payloads from Feature 24A input envelopes.
- Validate responses with Feature 24B.
- Record validated decisions in `agent_runs`.
- Keep draft update creation disabled by default until Feature 23B/23C are
  complete.

#### Client/UI Scope

- No UI.

#### Acceptance Criteria

- AI can remain disabled locally.
- Dry-run extraction can validate ignore/create-shaped responses.
- No contributor-facing update is created from dry-run output.
- Dry-run output is stored only as agent-run audit metadata.
- Invalid model output fails closed and follows existing worker retry behavior.

---

### Feature 24D - Model-Backed Source Event Extraction

#### Goal

Use the enterprise OpenAI-compatible endpoint and approved rulebook to convert
source events into contributor-reviewable draft updates.

#### Backend Scope

- Load the correct source rulebook during worker processing.
- Build a structured model input from source event, connected source, partner,
  and source metadata.
- Call the AI runtime with timeout and retry settings.
- Validate model JSON before creating any pending update.
- Record `agent_runs` with model, rulebook trace version, status, and safe
  technical output.
- Fall back to no update on invalid model output rather than creating unsafe
  drafts.

#### Client/UI Scope

- Pending Updates continue to be contributor-reviewed before approval.
- Any additional indicators must come from Feature 23B decisions.

#### Acceptance Criteria

- Approved source events can create draft updates through the model path.
- Invalid or low-confidence output does not silently create bad updates.
- Agent run audit data records model and rulebook traceability.
- Local development can keep AI disabled.

---

### Feature 24C.1 - Controlled AI Dry-Run Probe

Status: implemented locally.

#### Goal

Provide a safe one-off command to validate the real enterprise OpenAI-compatible
endpoint without writing source events, payloads, or partner updates.

#### Backend Scope

- Add a backend package tool runnable with `python -m`.
- Build an in-memory synthetic source event.
- Force dry-run extraction only for the probe process.
- Call the Feature 24C adapter.
- Validate output with Feature 24B.
- Print a redacted JSON report.

#### Client/UI Scope

- No UI.

#### Acceptance Criteria

- Probe requires AI runtime configuration.
- Probe does not print secret values.
- Probe does not write to the database.
- Probe reports zero partner update writes.
- Probe can be run inside the same backend Docker image used by API/worker.

---

## 4. Explicit Backlog

These are intentionally not in the first backend/agentic feature plan unless
later promoted:

- Dedicated Admin Health / Audit screen.
- Word Report download UI.
- PowerPoint export.
- Admin rulebook editing.
- Workstream admin UI.
- Self-service signup.
- Self-service forgot password.
- Full artifact history UI.
- Mobile-first redesign.

## 5. Design-Pending Items

The following UI designs are pending from Figma/user:

1. Contributor Connected Sources.
2. Admin Global Integrations.
3. Admin Connected Source Approvals.

Once those designs arrive, they should be inserted into:

- Feature 12.
- Feature 13.
- Feature 14.

If the Figma designs introduce new UI states or workflows, this plan should be revised before implementation starts.
