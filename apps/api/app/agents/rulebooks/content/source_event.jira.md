---
name: source_event.jira
version: production-2026-08-11
status: production
owner: developer
---

# Jira Source Event Extraction Rulebook

## Purpose

Convert approved Jira issue source events into contributor-reviewable draft
updates for Cloud AI Software Ecosystem Updates.

The agent must produce grounded, bulleted update text only when a Jira event
contains business-relevant facts for partner readiness, progress, risk,
timeline, dependency, action, priority, evidence, or partner impact.

All generated updates enter Pending Updates first. Nothing is approved
automatically.

## Input Contract

The agent receives one approved Jira connected source event at a time with:

- Partner and connected-source identity.
- Jira issue source URL.
- Jira event type and event timestamp.
- Jira issue metadata, changed fields, and retained source payload reference.
- Approved connected-source metadata.
- Idempotency key and source event ID.

Use only facts present in the source event, Jira issue fields, Jira comments,
linked evidence, source metadata, or approved connected-source metadata.

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
- The Jira source item's own timestamp determines the update month. A comment
  from April creates an April update, a comment from June creates a June update,
  and a comment from July creates a July update, even if all comments are fetched
  during a later month.
- Do not repeat prior-month Jira facts in a later month just because a later
  fetch included older comments as context. Older comments may provide context
  for dedupe and grounding, but the created update must be based only on the
  source item for that month.
- Extract only net-new facts introduced or changed by the current Jira source
  item. Do not repeat same-month facts from earlier Jira comments or events when
  the current comment merely acknowledges, references, or summarizes them.
- If a Jira comment repeats earlier context and adds one new grounded fact,
  create a draft with only the new fact or facts. If it adds no net-new fact,
  ignore it.
- Acknowledgements such as "helpful", "noted", "thanks", "confirmed", or similar
  wording are not new facts unless they change status, timeline, commitment,
  priority, risk, dependency, owner, or next action.
- Do not extract facts from acknowledgement clauses such as "the X estimate is
  helpful" or "noted on X"; those clauses refer to earlier information and are
  not net-new source facts.
- Remove conversational noise such as greetings, thanks, apologies, sign-offs,
  vacations, and acknowledgements when they add no business meaning.
- Do not add invented uncertainty phrasing such as "needs confirmation."

## Allowed Jira Events

Process only these events:

- Issue created.
- Status changed.
- Comment added.
- Due date or target month changed.
- Priority or severity changed.
- Linked issue or dependency changed.
- Attachment or document reference added.

Assignee or owner changes are out of scope for the first production Jira
rulebook unless they are present inside another allowed event and clearly change
what needs to happen next.

## Extraction Rules

Create a draft update when the Jira event adds or changes a grounded fact in one
or more of these categories:

- New blocker, risk, or issue.
- Status or progress change that affects partner readiness.
- Milestone, due date, or target month change.
- Priority or severity change.
- New dependency or linked issue.
- New document or evidence that changes the monthly narrative.
- Decision or leadership ask.
- Customer or partner impact.
- Ownership or action clarification when it changes what needs to happen next.
- Action-request comments that ask for target dates, shareable-version timing,
  blockers, gaps, dependencies, SAP-facing inputs, priority, severity, review,
  or next actions. The request itself is a grounded update even when the answer
  or final date is not yet present.

Write the update as clean monthly progress-summary lines. Names may be used only
when ownership or action is relevant and explicitly grounded. Preserve
approximate timing exactly when grounded, such as `~6 weeks` or `Aug./Sept.`

## Ignore Rules

Ignore Jira events when they do not affect status, risk, timeline, dependency,
action, priority, severity, evidence, or partner impact.

Do not ignore a Jira comment solely because it is phrased as a request or
question. If the comment explicitly asks for business-relevant target dates,
blockers, dependencies, priority, severity, review, evidence, or next actions,
create a grounded draft from that request and set `needs_human_attention=true`
when appropriate.

Always ignore:

- Formatting-only edits.
- Duplicate comments or repeated status with no new information.
- Thank-you or acknowledgement comments.
- Bot-generated or automation-only Jira noise.
- Label, tag, watch, or vote changes with no business meaning.
- Events outside the approved connected Jira issue scope.
- Assignee or owner changes outside the allowed-event exception above.
- Chatter that does not affect status, risk, timeline, dependency, action, or
  partner impact.

## Dedupe And Conflict Rules

- Exact duplicate Jira events must not create duplicate Pending Updates.
- Webhook redelivery must be ignored by idempotency key.
- If two different Jira events say essentially the same thing, keep only the
  first draft unless the later event adds new facts.
- If a later Jira event updates or corrects a previous fact, create a new
  Pending Update instead of silently editing the old one.
- One Jira event creates at most one draft update.
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
    "source_label": "Actual Jira issue title or approved connected-source title",
    "source_url": "https://jira.example.com/browse/KEY-123",
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
`Source: Jira Link Title` with the actual Jira issue or connected-source title
embedded as the Jira link. Never return the literal placeholder `Jira link
title`.

## Golden Examples

### Create update: July progress comment

Input: comment says initial full repository expected in `~6 weeks`, incremental
versions available sooner, no major blockers, help needed finding an SVE expert,
SAP AGI CPU evaluation in progress with possible CRB in Aug./Sept.

Expected summary lines:

- Initial full repository of learning material expected in ~6 weeks, with
  incremental versions available sooner.
- No major blockers identified.
- Assistance needed to find an SVE expert for deeper review.
- SAP's AGI CPU evaluation is in progress, with a potential CRB delivery in
  Aug./Sept.

### Create update: course scoping progress

Input: draft scoping document is available/shared, next steps involve proposing
course material based on SAP feedback.

Expected summary lines:

- Draft scoping document for the training course is available for review.
- Next steps involve proposing course material based on SAP feedback.

### Create update: follow-up comment with repeated acknowledgements

Input: later comment says the `~6-week estimate` is helpful, says ATG support is
noted, and then adds that SAP AGI CPU evaluation is starting, legal teams are
working through equipment loan and collaboration agreements, SAP may receive a
CRB in Aug./Sept., and `(4) QS A1 systems` are planned for performance
benchmarking in October.

Expected summary line:

- SAP's AGI CPU evaluation is starting while legal teams work through equipment
  loan and collaboration agreements; current timeline may provide SAP with a CRB
  in Aug./Sept. and 4 QS A1 systems for performance benchmarking in October.

Do not extract the `~6-week estimate` or ATG support facts from this source item
because they appear only as acknowledgements of earlier comments.

### Ignore: thank-you only

Input: `Thanks for the update, no worries on the delay.`

Expected decision: ignore.

### Ignore: formatting/edit only

Input: Jira description formatting changed, no field or factual meaning changed.

Expected decision: ignore.

### Borderline create: action request without firm date

Input: comment asks for target date, blockers/gaps, and whether priority should
change due to SAP / AGI CPU impact.

Expected summary line:

- Target date, blockers, SAP-facing input needs, and priority should be reviewed
  for the course material.

Expected flags: `needs_human_attention=true`.
