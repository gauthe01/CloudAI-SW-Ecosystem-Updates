# Pending Tasks And Blockers

This is the living tracker for unresolved product, engineering, integration,
and deployment tasks for Cloud AI Software Ecosystem Updates.

## Active Blockers

### Slack Live Webhook Validation

Status: pending external reachability.

The Slack backend implementation is complete locally, but Slack cannot call
`localhost`. To complete live validation, the API must be reachable through a
public HTTPS URL.

Required next steps:

- Deploy the API behind HTTPS on AWS, or expose local API temporarily with a
  tunnel such as ngrok or Cloudflare Tunnel.
- Set Slack Event Subscriptions Request URL to:
  - local tunnel: `https://<public-tunnel-url>/api/webhooks/slack/events`
  - AWS: `https://<api-domain>/api/webhooks/slack/events`
- Configure Slack app event subscriptions for channel messages and thread
  replies as required by the product scope.
- Ensure the Slack bot is invited to the contributor-configured channel.
- Create a contributor Slack Connected Source with channel name, channel ID, and
  bot-invited confirmation.
- Admin approves the Connected Source so it becomes active.
- Send a meaningful Slack message and confirm a Pending Update is created.

### Jira Live Webhook URL Replacement

Status: pending external reachability and Jira webhook setup.

The Jira backend credentials are configured locally, but Jira cannot call
`localhost`. Before live Jira webhook validation, the webhook URL shown in Admin
Global Integrations must be replaced with a public HTTPS URL, just like Slack.

Required next steps:

- Deploy the API behind HTTPS on AWS, or expose the local API temporarily with a
  tunnel such as ngrok or Cloudflare Tunnel.
- Replace the local Jira webhook URL:
  - local only: `http://localhost:8000/api/webhooks/jira/events`
  - AWS: `https://<api-domain>/api/webhooks/jira/events`
- Configure Jira webhook delivery to the public HTTPS URL.
- Keep the same Jira webhook secret in the app and Jira webhook configuration.
- Validate Jira receives HTTP 200 from the webhook endpoint.
- Confirm a real Jira issue/comment/update event creates a Pending Update.

### Confluence Live Webhook URL Replacement

Status: pending external reachability and Confluence webhook setup.

The Confluence backend credentials are configured locally, but Confluence cannot
call `localhost`. Before live Confluence webhook validation, the webhook URL
shown in Admin Global Integrations must be replaced with a public HTTPS URL,
just like Slack and Jira.

Required next steps:

- Deploy the API behind HTTPS on AWS, or expose the local API temporarily with a
  tunnel such as ngrok or Cloudflare Tunnel.
- Replace the local Confluence webhook URL:
  - local only: `http://localhost:8000/api/webhooks/confluence/events`
  - AWS: `https://<api-domain>/api/webhooks/confluence/events`
- Configure Confluence webhook delivery to the public HTTPS URL.
- Keep the same Confluence webhook secret in the app and Confluence webhook
  configuration.
- Validate Confluence receives HTTP 200 from the webhook endpoint.
- Confirm a real Confluence page update creates a Pending Update.

### GitHub Live Webhook URL Replacement

Status: pending external reachability and GitHub webhook setup.

The GitHub backend implementation is complete locally, but GitHub cannot call
`localhost`. Before live GitHub webhook validation, the webhook URL shown in
Admin Global Integrations must be replaced with a public HTTPS URL, just like
Slack, Jira, and Confluence.

Required next steps:

- Deploy the API behind HTTPS on AWS, or expose the local API temporarily with a
  tunnel such as ngrok or Cloudflare Tunnel.
- Replace the local GitHub webhook URL:
  - local only: `http://localhost:8000/api/webhooks/github/events`
  - AWS: `https://<api-domain>/api/webhooks/github/events`
- Configure GitHub webhook delivery to the public HTTPS URL.
- Keep the same GitHub webhook secret in the app and GitHub webhook
  configuration.
- Validate GitHub receives HTTP 200 from the webhook endpoint.
- Confirm a real repository, issue, or pull request event creates a Pending
  Update for the matching approved source.

### Test Data Isolation

Status: resolved locally.

The API test suite now uses a separate local Postgres database:

- `cloud_ai_software_ecosystem_updates_test`

This prevents automated test cleanup from wiping locally entered admin
integration credentials in the main developer database.

Required next steps:

- Keep tests pointed at the isolated test database.
- Consider a disposable containerized test database later for CI.

## Product / UX Tasks

### UI Visual Parity

Status: pending later UI pass.

The current UI is product-functional scaffolding. It does not yet fully match
the previous project visual style.

Required next steps:

- Reuse the previous project's visual patterns where already approved.
- Avoid changing screen behavior that was marked "keep as-is" during UI review.
- Rework only the pending screens that required new Figma prompts/designs.
- Run browser walkthroughs after the backend feature set stabilizes.

### Connected Sources UX

Status: partially implemented.

Contributor Connected Sources and Admin approvals exist, but each integration
still needs source-specific polish as live integrations are added.

Required next steps:

- Confirm contributor source forms for Jira, SharePoint, Confluence, GitHub, and
  Slack match the final product wording.
- Keep training/committed sources separate from general Resource Links.
- Keep Resource Links visible in Partner Metadata, including connected-source
  links where relevant.

## Engineering Tasks

### Feature 17 - Jira Connected Source Processing

Status: implemented locally.

Required next steps:

- Configure Jira global credentials in Admin Global Integrations.
  - Development may temporarily use a personal PAT as `service_token`.
  - Before team/shared deployment, replace it with the Jira service-account PAT.
- Create and approve a contributor Jira issue Connected Source.
- Expose the API through AWS HTTPS or a local tunnel.
- Replace the local admin-console Jira webhook URL with the deployed public URL.
- Configure Jira webhook delivery to:
  - `https://<api-domain>/api/webhooks/jira/events`
- Validate a real Jira issue event creates a Pending Update.
- Later: add Jira MCP/service enrichment for richer ticket-level extraction.
- Keep no-polling behavior.

### Feature 18 - SharePoint Connected Source Processing

Status: implemented locally.

Required next steps:

- Configure SharePoint / Microsoft Graph credentials in Admin Global
  Integrations, including Client State.
- Create and approve a contributor SharePoint file Connected Source.
- Expose the API through AWS HTTPS or a local tunnel.
- Configure Microsoft Graph change notification delivery to:
  - `https://<api-domain>/api/webhooks/sharepoint/events`
- Validate Graph notification URL using the validation token response.
- Validate a real Graph notification can be matched to a single approved file.
- Add live Graph file download through the configured app credentials.
- Later: add full DOCX/PPTX/XLSX/PDF semantic extraction using the
  developer-owned SharePoint/document rulebook.
- Keep raw Graph notifications out of retained payload storage.

### Feature 19 - Confluence Connected Source Processing

Status: implemented locally.

Required next steps:

- Configure Confluence global credentials in Admin Global Integrations.
  - Base URL
  - Service Token
  - Webhook Secret
- Create and approve a contributor Confluence page Connected Source.
- Expose the API through AWS HTTPS or a local tunnel.
- Configure Confluence webhook delivery to:
  - `https://<api-domain>/api/webhooks/confluence/events`
- Keep the same Confluence webhook secret in the app and Confluence webhook
  configuration.
- Validate a real Confluence page update creates a Pending Update.
- Later: add Confluence REST/MCP page fetch enrichment for current page bodies.
- Keep no-polling behavior.

### Feature 20 - GitHub Connected Source Processing

Status: implemented locally.

Required next steps:

- Configure GitHub global credentials in Admin Global Integrations.
  - App ID
  - Private Key
  - Webhook Secret
- Create and approve a contributor GitHub repository, issue, or pull request
  Connected Source.
- Expose the API through AWS HTTPS or a local tunnel.
- Configure GitHub webhook delivery to:
  - `https://<api-domain>/api/webhooks/github/events`
- Keep the same GitHub webhook secret in the app and GitHub webhook
  configuration.
- Validate a real GitHub event creates a Pending Update for the matching
  approved source scope.
- Later: add GitHub App/API enrichment for repository, issue, PR, and comment
  details.
- Keep no-polling behavior.

### Feature 21 - Presenter Intelligence And Draft Email

Status: implemented locally.

Required next steps:

- Run a browser walkthrough with presenter login after enough approved data is
  present.
- Improve visual parity with the legacy Presenter View during the later UI pass.
- Add model-backed presenter intelligence using the developer-owned rulebook.
- Add Ask AI orchestration if promoted from placeholder to live feature.
- Keep PowerPoint export and Word report download out of v1 unless promoted.

### Agentic Extraction Layer

Status: runtime and rulebook framework implemented locally; first production
rulebook interview pending.

Current source processing uses deterministic/local rules. The product remains
agentic in architecture, but full AI extraction and reasoning still need to be
implemented.

Required next steps:

- Configure the approved enterprise OpenAI-compatible endpoint:
  - `AI_PROVIDER=enterprise_openai_compatible`
  - `AI_BASE_URL`
  - `AI_API_KEY`
  - `AI_MODEL_UPDATE_EXTRACTION`
  - `AI_MODEL_REPORTING`
- Validate API and worker containers can reach the enterprise endpoint from the
  target AWS network.
- Add `AI_CA_BUNDLE` if the enterprise endpoint requires a private corporate CA.
- Replace placeholder developer-owned rulebooks with approved business rules for
  Slack, Jira, SharePoint, Confluence, GitHub, update quality, presenter
  intelligence, executive email, and decision board analysis.
- Complete Feature 23B before replacing any placeholder rulebook:
  - choose the first rulebook
  - capture event scope
  - capture extraction and ignore rules
  - capture language rules
  - capture output JSON contract
  - capture dedupe and traceability rules
  - collect golden test examples
- Add model-backed extraction once source contracts are stable.

### Feature 23B - Rulebook Business Interview

Status: next planned agentic feature.

Feature 23B is required before model-backed extraction. It is the interview and
decision-capture feature that turns a placeholder rulebook into approved product
behavior.

Required next steps:

- Choose the first rulebook to finalize, recommended: Jira.
- Interview the product owner one question at a time.
- Write the decision pack before implementation.
- Capture any UI implications for Pending Updates, Connected Sources, or Admin
  approvals.
- Decide whether to implement Feature 23C as a separate rulebook-content update
  before Feature 24.

### Feature 24A - Agent Extraction Infrastructure

Status: implemented locally.

Required next steps:

- Keep Feature 23B and Feature 23C open as business-rule gates.
- Add Feature 24B model output contract and validation.
- Do not enable model-backed pending update creation until an approved
  production rulebook exists.
- Later, replace source-specific deterministic processors with the shared
  extraction path only after behavior is tested source by source.

### Feature 24B - Model Output Contract And Validation

Status: implemented locally.

Required next steps:

- Use the validation contract from any future model adapter.
- Keep pending-update database writes disabled until model output is validated
  and Feature 23B/23C are complete.
- Decide later whether confidence, reasoning category, attention flag, and event
  importance should be shown in Contributor Pending Updates.
- Store agent runs, rulebook versions, and output JSON for traceability.
- Keep contributor review before updates become official.

### Feature 24C - Model Adapter And Dry-Run Extraction

Status: implemented locally.

Required next steps:

- Keep `AI_SOURCE_EVENT_EXTRACTION_MODE=infrastructure_only` by default.
- Use `dry_run` only when enterprise OpenAI-compatible credentials and endpoint
  access are available in the target environment.
- Review dry-run `agent_runs.output_json` before allowing any model-created
  pending update writes.
- Complete Feature 23B and Feature 23C before Feature 24D creates
  contributor-reviewable drafts from model output.
- Keep source-specific deterministic processors in place until each source is
  migrated to the shared agent path deliberately.

### Feature 24C.1 - Controlled AI Dry-Run Probe

Status: implemented locally; real enterprise endpoint probe succeeded from the
Docker API container on August 9, 2026.

Required next steps:

- Run the probe only after enterprise AI endpoint credentials are configured in
  the backend environment.
- Confirm the probe returns `status=succeeded`,
  `result.extraction_mode=model_dry_run`, and
  `database_writes.partner_updates=0`.
- If the endpoint rejects JSON response-format requests, adjust the adapter
  deliberately instead of weakening output validation.
- Keep the approved ARM root certificate available in local `certs/` for Docker
  runs and set `AI_CA_BUNDLE=/app/certs/ARM-Enterprise-PKI-Root-CA.pem`.
- Keep `truststore` in the backend runtime as the system-trust fallback when
  an explicit CA bundle is not configured.
- Use a valid proxy model name. `gpt-5o` is not available on the current
  endpoint/key; local dry-run validation uses `gpt-4o`.
- Keep long-running workers in `infrastructure_only` until real dry-run output
  is reviewed.

## Deployment Tasks

### AWS Runtime

Status: pending.

Required next steps:

- Choose final AWS runtime path:
  - EC2 plus Docker Compose for simpler first deployment, or
  - ECS/Fargate plus ALB for more production-shaped container orchestration.
- Provision managed Postgres, preferably RDS.
- Put API behind HTTPS using ALB and ACM certificate.
- Configure public API domain for webhooks.
- Move secrets to AWS Secrets Manager or SSM Parameter Store.
- Configure app environment variables in AWS.
- Add backup/restore plan for Postgres and uploaded files.

### External Integration Validation

Status: pending for all live providers.

Required next steps:

- Slack: validate token, bot install, channel access, event subscription.
- Jira: validate credentials, webhook secret, ticket access, MCP/service access.
- SharePoint: validate tenant/app credentials and file access.
- Confluence: validate service token and page access.
- GitHub: validate app credentials, webhook secret, and repository access.

### Backend Test Container

Status: pending.

Context:

- The API runtime container is intentionally production-lean.
- It installs the backend package without dev extras and does not include the
  `tests/` directory.
- As a result, `docker compose exec api python -m pytest` cannot run because
  `pytest` is not installed in the runtime image.

Required next steps:

- Add a separate API test Docker target or Compose service, for example
  `api-tests`.
- Install backend dev extras in that test image with `.[dev]`.
- Copy or mount `apps/api/tests` only for the test image/service.
- Run backend tests through the test service, not the production API runtime
  container.
- Keep the production API and worker images free of test-only dependencies.

## Documentation Tasks

### Infrastructure Document

Status: partly drafted, needs finalization after AWS choice.

Required next steps:

- Finalize runtime diagram for selected AWS deployment model.
- Document container boundaries: web, API, worker, Postgres/RDS.
- Document environment variables and secrets ownership.
- Document webhook ingress path.
- Document data retention policy for source payloads.
- Document operational runbook for local and AWS deployments.
