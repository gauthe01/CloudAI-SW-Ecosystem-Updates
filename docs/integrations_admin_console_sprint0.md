# Integrations Admin Console - Sprint 0 Baseline

Created: 2026-08-04 15:56 PDT

## Purpose

Sprint 0 is a safety and grounding iteration for the Integrations Admin Console work. It does not implement the new UI, change routes, alter schemas, or modify integration behavior. Its only product is a safe branch plus a documented baseline for Sprint 1.

## Branch And Worktree Baseline

Implementation branch:

```text
codex/integrations-admin-console
```

The branch was created from `main` with an already-dirty worktree. These files were modified or untracked before Sprint 0 documentation edits and must be treated as pre-existing user/project work, not reverted as part of this activity:

```text
 M .dockerignore
 M .env.production.template
 M .gitignore
 M agents/agent_1b/agent.py
 M agents/agent_1d/agent.py
 M agents/agent_2a/agent.py
 M agents/agent_6a/agent.py
 M agents/agent_6a/skills.md
 M auth/auth.py
 M core/config.py
 M core/database.py
 M core/doc_parser.py
 M core/intelligence_agent.py
 M core/ppt_parser.py
 M core/rich_text.py
 M dashboard/main.py
 M dashboard/templates/admin.html
 M dashboard/templates/admin_integrations.html
 M dashboard/templates/admin_train.html
 M dashboard/templates/base.html
 M dashboard/templates/home.html
 M dashboard/templates/intelligence.html
 M dashboard/templates/partner_selection.html
 M db/init_db.py
 M docs/aws_production_migration.md
 M tests/test_exec_email_agent.py
 M tests/test_ingestion_platform.py
 M tests/test_ppt_parser.py
?? core/smart_analysis.py
?? dashboard/templates/account_view_menu.html
?? dashboard/templates/smart_analysis.html
?? db/arm_automation.db.backup_inline_links_20260716_130915
?? db/arm_automation.db.backup_links_20260716_120028
?? docs/intelligence_layer_rag_diagrams.md
?? tests/test_shared_mailbox_polling.py
?? tests/test_smart_analysis.py
```

## Current Architecture

The project is a FastAPI application using Jinja templates and static CSS/JS, not a React application. Sprint 1 should adapt the Figma/prompt design to the current server-rendered stack.

Primary files and helpers for the current integrations surface:

- `dashboard/main.py`
  - `_admin_integrations_context`
  - `_integration_card_state`
  - `_slack_admin_context`
  - `admin_integrations_overview`
  - `admin_slack_detail`
  - `admin_jira_setup_step`
- `dashboard/templates/admin_integrations.html`
  - current overview grid
  - Slack detail
  - Jira setup wizard
- `core/integration_secrets.py`
  - encrypted secret set/get/status helpers
- Existing integration summary helpers:
  - `agents/agent_1f/agent.py::github_admin_summary`
  - `agents/agent_1e/agent.py::m365_files_admin_summary`
  - `agents/agent_1d/agent.py::shared_mailbox_admin_summary`

## Current Routes And Actions

Read routes:

- `GET /admin/integrations`
- `GET /admin/integrations/slack`
- `GET /admin/integrations/jira/setup/{step}`

Existing action routes used by the current surface:

- `POST /api/integrations/slack/mapping`
- `POST /api/integrations/slack/mapping/{mapping_id}/toggle`
- `POST /api/integrations/slack/mapping/{mapping_id}/delete`
- `POST /admin/integrations/slack/sync`
- `POST /api/integrations/m365-files/documents`
- `POST /api/integrations/m365-files/documents/{document_id}/remove`
- `POST /m365-files/poll`
- `POST /shared-mailbox/poll`
- `POST /api/integrations/github/config`
- `POST /github/poll`
- `POST /api/integrations/jira/test`
- `POST /api/integrations/jira/discover`
- `POST /api/integrations/jira/filter`
- `GET /api/integrations/jira/mapping`
- `POST /api/integrations/jira/mapping`
- `GET /api/integrations/jira/preview`
- `POST /api/integrations/jira/enable`

Sprint 1 should not remove or rewrite these routes. If new overview links are introduced, they should keep existing working destinations intact.

## Figma And Prompt Mapping

Figma file:

```text
fileKey: nlnQ5KCtpqyxP5Dw1Wgrth
page node: 0:1 (Page 1)
```

The shared Figma URL points to the page root, not a node-specific overview frame. MCP metadata confirms the file has one top-level page. A concrete detail-frame node was verified during grounding:

```text
539:401 - OAI-09 · Test Success
```

That frame confirms the visual language Sprint 1 should follow: navy top nav, light gray app background, compact white cards, Inter typography, status badges, masked secret fields, and top-right toast behavior. The OpenAI designs are Azure OpenAI-oriented, which matches this repo's existing Azure/OpenAI runtime configuration better than a generic OpenAI-only model.

Before Sprint 1 implementation, the overview frame must be selected or linked directly in Figma so `get_design_context` and `get_screenshot` can be fetched for the exact overview node. Expected overview design target from the prompt/current template naming is `AD-INT-01` / integrations overview, but the exact node id was not exposed by the page-root link alone.

## Test Baseline

`pytest` is not installed in the default Python or the project virtualenv:

```text
python3 -m pytest ... -> No module named pytest
./env/bin/python -m pytest ... -> No module named pytest
```

The stdlib `unittest` runner is available:

```text
./env/bin/python -m unittest ...
```

Baseline command attempted:

```text
./env/bin/python -m unittest \
  tests.test_ingestion_platform.IngestionPlatformTests.test_admin_integrations_figma_routes_render_without_secret_leak \
  tests.test_ingestion_platform.IngestionPlatformTests.test_admin_slack_detail_renders_and_manages_channel_mapping \
  tests.test_github_integration \
  tests.test_shared_mailbox_polling
```

Result:

- The two current admin integration route tests passed.
- The broader GitHub integration test module failed under this runner during setup because `source_items` was missing in the temporary database.
- Shared mailbox tests completed after the GitHub setup failures were reported.

Sprint 1 should use the two admin route tests as the immediate smoke baseline and should not treat the broader GitHub unittest failure as caused by the new overview work unless it changes after implementation.

## Sprint 1 Boundary

Sprint 1 is limited to the main `/admin/integrations` overview screen.

Allowed in Sprint 1:

- Adjust overview-specific view model data if needed.
- Redesign the overview cards and layout to match the Figma/prompt direction.
- Add overview-specific tests and secret-leak assertions.
- Preserve existing links to Slack detail and Jira setup routes.

Not allowed in Sprint 1:

- Build detail pages for individual integrations.
- Change credential storage behavior.
- Add database migrations.
- Remove or rewrite existing integration action routes.
- Introduce React, Tailwind, a frontend build pipeline, or new dependencies.
