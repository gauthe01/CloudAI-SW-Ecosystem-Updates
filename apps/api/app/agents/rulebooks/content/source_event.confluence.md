---
name: source_event.confluence
version: production-2026-08-11
status: production
owner: developer
---

# Confluence Source Event Extraction Rulebook

## Purpose

Convert approved Confluence page events and extracted page content into
contributor-reviewable draft updates for Cloud AI Software Ecosystem Updates.

The agent must create updates only from grounded page content or approved page
metadata that changes partner readiness, progress, risk, timeline, dependency,
action, priority, evidence, or partner impact.

All generated updates enter Pending Updates first. Nothing is approved
automatically.

## Input Contract

The agent receives one approved Confluence page source event at a time with:

- Partner and connected-source identity.
- Confluence page source URL.
- Page title, page metadata, event type, and event timestamp.
- Extracted readable page content when available.
- Retained payload reference.
- Approved connected-source metadata.
- Idempotency key and source event ID.

Use only facts present in the page event, extracted page content, page comments
when in scope, linked evidence, source metadata, or approved connected-source
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
  labels, version numbers, estimates, and benchmark values.
- Preserve relevant links found in source items in the same update line they
  support. Do not drop a source-item link when the linked reference is part of
  the grounded update.
- The Confluence source item's own timestamp determines the update month. A page
  edit or in-scope comment from April creates an April update, and one from July
  creates a July update, even if both are fetched during a later month.
- Do not repeat prior-month Confluence facts in a later month just because a
  later fetch included older page versions or comments as context. Older source
  items may provide context for dedupe and grounding, but the created update
  must be based only on the source item for that month.
- Extract only net-new facts introduced or changed by the current Confluence
  source item. Do not repeat same-month facts from earlier page versions or
  comments when the current source item merely acknowledges, references, carries
  forward, or summarizes them.
- If a Confluence source item repeats earlier context and adds one new grounded
  fact, create a draft with only the new fact or facts. If it adds no net-new
  fact, ignore it.
- Acknowledgements such as "helpful", "noted", "thanks", "confirmed", or similar
  wording are not new facts unless they change status, timeline, commitment,
  priority, risk, dependency, owner, or next action.
- Remove page boilerplate when it adds no business meaning.

## Allowed Confluence Events

Process only these events:

- Approved connected Confluence page is created.
- Approved connected Confluence page is updated.
- Page comment added, only if comments are in connected-source scope.
- Page title changes only if the change affects business meaning.
- Page content changes that include progress, blocker, timeline, priority,
  dependency, action, evidence, or partner impact.

## Extraction Rules

Create a draft update when the Confluence event or extracted page content adds
or changes a grounded fact in one or more of these categories:

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

Ignore Confluence events when they do not affect status, risk, timeline,
dependency, action, priority, severity, evidence, or partner impact.

Always ignore:

- Permission-only changes.
- Watch, like, or reaction changes.
- Label-only changes unless the label changes business status or severity.
- Page moved with no content or business meaning.
- Formatting-only edits.
- Duplicate page update with no extracted content change.
- Events outside the approved connected page scope.

## Dedupe And Conflict Rules

- Exact duplicate Confluence events must not create duplicate Pending Updates.
- Webhook redelivery must be ignored by idempotency key.
- If two page versions say essentially the same thing, keep only the first draft
  unless the later version adds new facts.
- If a later page version updates or corrects a previous fact, create a new
  Pending Update instead of silently editing the old one.
- One Confluence event creates at most one draft update.
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
    "source_label": "Page Title",
    "source_url": "https://confluence.example.com/page",
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
`Source: Page Title` with the title embedded as the Confluence link.

## Golden Examples

### Create update: page progress change

Input: page says `Elastic vector search validation completed; next benchmark
review scheduled for October.`

Expected summary lines:

- Elastic vector search validation completed.
- Next benchmark review is scheduled for October.

### Create update: dependency added

Input: page update adds `Delivery depends on access to partner test environment
by Sep 10.`

Expected summary line:

- Delivery depends on access to the partner test environment by Sep 10.

### Ignore: label-only change

Input: label added or removed with no content or business status change.

Expected decision: ignore.

### Ignore: formatting-only page edit

Input: headings or table formatting changed, same facts.

Expected decision: ignore.

### Borderline create: page says priority is being reviewed

Input: `Priority is being reviewed after partner planning discussion,` with no
final outcome.

Expected summary line:

- Priority is being reviewed after the partner planning discussion.

Expected flags: `needs_human_attention=true`.
