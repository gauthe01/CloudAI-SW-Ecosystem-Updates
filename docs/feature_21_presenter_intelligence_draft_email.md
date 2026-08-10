# Feature 21 - Presenter Intelligence And Draft Email

Feature 21 delivers the first working Presenter View for Cloud AI Software
Ecosystem Updates.

## Scope

- Presenter-only read APIs:
  - `GET /api/presenter/partners`
  - `GET /api/presenter/updates`
  - `GET /api/presenter/partners/{partner_id}/metadata`
  - `GET /api/presenter/analysis`
  - `POST /api/presenter/draft-email`
- Presenter can read approved updates across all active partners.
- Presenter can filter updates by month, search text, and partner.
- Presenter can read partner metadata only when a single partner is selected.
- Presenter analysis returns:
  - executive summary
  - decision board
  - update count
  - partner count
  - source mix
- Draft email is generated from approved updates using a developer-owned local
  rulebook.
- No PowerPoint export.
- No Word report UI.
- No presenter edit actions.

## Access Model

Presenter APIs require the `presenter` role. They do not require contributor
partner assignment.

This matches the product rule that Contributor View is assignment-scoped, while
Presenter View is a read-only wider visibility surface.

## UI Behavior

The Presenter View now replaces the prior placeholder panels with working
client-side surfaces:

- Executive Summary
- Decision Board
- Partner Intelligence
- Draft Email

All tabs share the same controls:

- search approved updates
- partner selector with All Partners default
- cycle/month selector

Partner metadata is shown only after selecting one partner. All Partners shows
approved updates and prompts the presenter to select a partner for metadata.

## Processing Rule

The current analysis and draft email logic is deterministic and
developer-owned:

- summarize counts and most active partner signals
- build the decision board from amber/red/high/critical metadata risks
- draft email from approved updates only
- limit email body to a compact first set of approved updates

This is the placeholder presenter intelligence layer. Later agentic extraction
can use richer rulebooks, model-backed reasoning, and traceable agent runs.

## Not In Scope

- Presenter editing of reports or approved updates.
- PowerPoint export.
- Word report download.
- Admin-side rulebook editing.
- Model-backed executive summary generation.
- Ask AI chat orchestration.
- Visual parity pass against the legacy presenter screen.
