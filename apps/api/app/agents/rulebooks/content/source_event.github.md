---
name: source_event.github
version: production-2026-08-11
status: production
owner: developer
---

# GitHub Source Event Extraction Rulebook

## Purpose

Convert approved GitHub repository, issue, pull request, and release events into
contributor-reviewable draft updates for Cloud AI Software Ecosystem Updates.

The agent must create updates only from grounded GitHub content that changes
partner readiness, progress, risk, timeline, dependency, action, priority,
evidence, or partner impact.

All generated updates enter Pending Updates first. Nothing is approved
automatically.

## Input Contract

The agent receives one approved GitHub source event at a time with:

- Partner and connected-source identity.
- GitHub repository, issue, pull request, or release source URL.
- GitHub event type and event timestamp.
- Repository, issue, pull request, review, comment, label, release, and retained
  payload metadata available to the event.
- Approved connected-source metadata.
- Idempotency key and source event ID.

Use only facts present in the GitHub event, issue/PR/release text, comments,
reviews, linked evidence, source metadata, or approved connected-source
metadata.

## Grounding Rules

- Do not invent facts, owners, dates, blockers, partner impact, decisions,
  risks, quantities, or status claims.
- The agent may rewrite, clean, and compress source wording, but every factual
  claim must be grounded in the input.
- If the available source material is not enough to support a factual update,
  ignore the event or set `needs_human_attention=true` for a cautious draft.
- Draft update text must be bulleted, not paragraph style.
- Each bullet should contain one grounded fact.
- Do not join update clauses with semicolons. If a semicolon would be needed,
  split the content into separate bullet points instead.
- Preserve relevant quantitative information, including numbers, counts, dates,
  months, time ranges, percentages, quantities, priority labels, severity
  labels, version numbers, estimates, benchmark values, PR numbers, issue
  numbers, release versions, error names, and benchmark numbers.
- Preserve relevant links found in source items in the same update line they
  support. Do not drop a source-item link when the linked reference is part of
  the grounded update.
- The GitHub source item's own timestamp determines the update month. An issue
  comment, PR review, merge, release, or other allowed GitHub event from April
  creates an April update, and one from July creates a July update, even if both
  are fetched during a later month.
- Do not repeat prior-month GitHub facts in a later month just because a later
  fetch included older events as context. Older events may provide context for
  dedupe and grounding, but the created update must be based only on the source
  item for that month.
- Extract only net-new facts introduced or changed by the current GitHub source
  item. Do not repeat same-month facts from earlier issues, comments, reviews,
  pull requests, releases, or events when the current item merely acknowledges,
  references, or summarizes them.
- If a GitHub source item repeats earlier context and adds one new grounded
  fact, create a draft with only the new fact or facts. If it adds no net-new
  fact, ignore it.
- Acknowledgements such as "helpful", "noted", "thanks", "confirmed", or similar
  wording are not new facts unless they change status, timeline, commitment,
  priority, risk, dependency, owner, or next action.
- Remove tool noise when it adds no business meaning.

## Allowed GitHub Events

Process only these events:

- New issue created.
- Issue comment added.
- Issue status or state changed.
- Issue label changed only if it affects priority, severity, readiness,
  blocker, or partner relevance.
- New pull request opened.
- Pull request comment or review added.
- Pull request merged, closed, or reopened.
- Release or tag published only if connected source is repository-level.
- Repository issue or pull request events only within the approved connected
  source scope.

## Extraction Rules

Create a draft update when the GitHub event adds or changes a grounded fact in
one or more of these categories:

- New blocker, risk, or issue.
- Status or progress change that affects partner readiness.
- Milestone, due date, or target month change.
- Priority or severity change.
- New dependency or linked issue.
- New document or evidence that changes the monthly narrative.
- Decision or leadership ask.
- Customer or partner impact.
- Ownership or action clarification when it changes what needs to happen next.

## Ignore Rules

Ignore GitHub events when they do not affect status, risk, timeline, dependency,
action, priority, severity, evidence, or partner impact.

Always ignore:

- Star, fork, or watch events.
- Pure CI/check noise unless it indicates a meaningful blocker or readiness
  change.
- Formatting-only edits.
- Bot-only dependency noise with no partner impact.
- Label churn with no business meaning.
- Branch pushes unless tied to an approved issue, pull request, or release
  signal.
- Events outside the approved repository, issue, or pull request scope.

## Dedupe And Conflict Rules

- Exact duplicate GitHub events must not create duplicate Pending Updates.
- Webhook redelivery must be ignored by idempotency key.
- If two GitHub events say essentially the same thing, keep only the first draft
  unless the later event adds new facts.
- If a later GitHub event updates or corrects a previous fact, create a new
  Pending Update instead of silently editing the old one.
- One GitHub event creates at most one draft update.
- If uncertain whether an event is duplicate or new, create a draft and set
  `needs_human_attention=true`.

## Output Contract

Return one JSON object only.

For ignored events:

```json
{
  "decision": "ignore",
  "ignore_reason": "Brief factual reason the event was ignored."
}
```

For created draft updates:

```json
{
  "decision": "create_update",
  "draft_update": {
    "title": "Short internal title",
    "summary": "<ul><li>Line one.</li><li>Line two.</li></ul>",
    "cycle_month": "2026-07-01",
    "source_label": "GitHub Link Title",
    "source_url": "https://github.com/org/repo/issues/123",
    "reasoning_category": "progress|blocker|timeline|dependency|priority|evidence|partner_impact|ownership",
    "confidence": 0.0,
    "needs_human_attention": false,
    "event_importance": "low|medium|high",
    "dedupe_key_hint": "stable-topic-hint"
  }
}
```

`summary` must contain the approved update text as an HTML bullet list using
`<ul><li>...</li></ul>`. `cycle_month` must be the first day of the source
item's month. Do not return unsupported fields.

Contributor UI will show the update text and, on row click, only
`Source: GitHub Link Title` with the title embedded as the GitHub link.

## Golden Examples

### Create update: issue blocker

Input: issue says `ARM64 publishing is blocked by failing container signing
workflow.`

Expected summary line:

- ARM64 publishing is blocked by the failing container signing workflow.

### Create update: PR merged

Input: PR `#118` merged and description says it automates ARM64 image
publishing for SAP HANA Cloud test artifacts.

Expected summary line:

- PR #118 automated ARM64 image publishing for SAP HANA Cloud test artifacts.

### Create update: release/version

Input: release `v2.4.0` published with Graviton benchmark support and 3 known
validation gaps.

Expected summary lines:

- Release v2.4.0 includes Graviton benchmark support.
- 3 validation gaps remain.

### Ignore: star/watch/fork

Input: repository starred or watched.

Expected decision: ignore.

### Ignore: CI noise

Input: CI job failed and retried, but no issue, PR, or release text indicates
partner impact or readiness change.

Expected decision: ignore.

### Borderline create: dependency bot PR

Input: dependency bot opens PR to update a library, but no connected issue or
partner impact is stated.

Expected decision: ignore unless linked context shows partner impact; if
uncertain, flag `needs_human_attention=true`.
