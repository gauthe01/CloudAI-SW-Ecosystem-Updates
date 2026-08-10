# Feature 23 - Developer-Owned Rulebook Framework

## Purpose

Feature 23 creates the rulebook framework for Cloud AI Software Ecosystem
Updates. Rulebooks are developer-owned markdown files that define how future AI
agents should extract, ignore, phrase, and structure outputs.

This feature intentionally does not finalize business language. The rulebooks
added here are placeholders so the backend can load, hash, validate, and trace
them before model-backed extraction begins.

## Backend Scope

- Add a packaged rulebook directory under `app/agents/rulebooks/content`.
- Add an explicit manifest of registered rulebooks.
- Add a `RulebookLoader` that validates names, loads markdown, parses front
  matter, validates required sections, and calculates a SHA-256 content hash.
- Add `trace_version` as `version:hash-prefix` so future `agent_runs` can record
  exactly which rulebook version shaped a model output.
- Keep rulebook loading independent of OpenAI calls.
- Keep all rulebook files in the API/worker image for local Docker and AWS.

## Registered Rulebooks

- `source_event.slack`
- `source_event.jira`
- `source_event.sharepoint`
- `source_event.confluence`
- `source_event.github`
- `update_quality`
- `presenter_intelligence`
- `executive_email`
- `decision_board`

## Rulebook File Contract

Each rulebook must:

- Start with front matter.
- Include `name`, `version`, and `status`.
- Have metadata `name` that matches the manifest key.
- Include the sections `## Purpose`, `## Input Contract`, and
  `## Output Contract`.
- Be loaded only through the registered manifest, not arbitrary file paths.

## Deployment Shape

Rulebooks are packaged into the same backend image used by the API and worker.
For the first AWS deployment, this is intentional:

- No extra container is needed.
- API and worker read the same developer-owned rulebook files.
- Rulebook changes are deployed through normal backend image promotion.
- Future admin-editable rulebooks are explicitly out of scope for now.

## Not In Scope

- No real prompt content finalization.
- No model call.
- No UI.
- No database migration.
- No contributor/admin rulebook editing.

## Next Step

Before Feature 24, complete Feature 23B: Rulebook Business Interview.

Feature 23B is the product-and-engineering gate where the product owner and
developer finalize the first real rulebook behavior, most likely Jira or Slack,
before any model-backed extraction is enabled.
