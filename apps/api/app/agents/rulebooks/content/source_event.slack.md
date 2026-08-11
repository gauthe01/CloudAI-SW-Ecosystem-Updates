---
name: source_event.slack
version: production-2026-08-11
status: production
owner: developer
---

# Slack Source Event Extraction Rulebook

## Purpose

Convert approved Slack channel messages and thread replies into
contributor-reviewable draft updates for Cloud AI Software Ecosystem Updates.

The agent must create updates only from grounded Slack content that changes
partner readiness, progress, risk, timeline, dependency, action, priority,
evidence, or partner impact.

All generated updates enter Pending Updates first. Nothing is approved
automatically.

## Input Contract

The agent receives one approved Slack source event at a time with:

- Partner and connected-source identity.
- Slack channel source URL.
- Slack event type and event timestamp.
- Channel name, channel ID, thread metadata, message metadata, and retained
  payload reference.
- Approved connected-source metadata.
- Idempotency key and source event ID.

Use only facts present in the Slack message, thread context supplied to the
agent, linked evidence, source metadata, or approved connected-source metadata.

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
- The Slack source item's own timestamp determines the update month. A message
  or thread reply from April creates an April update, and a reply from July
  creates a July update, even if both are fetched during a later month.
- Do not repeat prior-month Slack facts in a later month just because a later
  fetch included older messages as context. Older messages may provide context
  for dedupe and grounding, but the created update must be based only on the
  source item for that month.
- Extract only net-new facts introduced or changed by the current Slack source
  item. Do not repeat same-month facts from earlier messages or thread replies
  when the current message merely acknowledges, references, or summarizes them.
- If a Slack message repeats earlier context and adds one new grounded fact,
  create a draft with only the new fact or facts. If it adds no net-new fact,
  ignore it.
- Acknowledgements such as "helpful", "noted", "thanks", "confirmed", or similar
  wording are not new facts unless they change status, timeline, commitment,
  priority, risk, dependency, owner, or next action.
- Remove conversational noise such as greetings, thanks, apologies, sign-offs,
  vacations, and acknowledgements when they add no business meaning.

## Allowed Slack Events

Process only these events:

- New message in an approved connected channel.
- Thread reply in an approved connected channel.
- Edited message only if the edit adds or changes business facts.
- Shared link or file reference when the message text gives enough grounded
  context.

## Extraction Rules

Create a draft update when the Slack event adds or changes a grounded fact in
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

Ignore Slack events when they do not affect status, risk, timeline, dependency,
action, priority, severity, evidence, or partner impact.

Always ignore:

- Emoji or reaction-only events.
- Joins, leaves, and channel admin messages.
- Bot or system messages.
- Thank-you or acknowledgement-only messages.
- Deleted messages.
- Formatting-only edits.
- Messages outside the approved connected channel.

## Dedupe And Conflict Rules

- Exact duplicate Slack events must not create duplicate Pending Updates.
- Webhook redelivery must be ignored by idempotency key.
- If two Slack events say essentially the same thing, keep only the first draft
  unless the later event adds new facts.
- If a later event updates or corrects a previous fact, create a new Pending
  Update instead of silently editing the old one.
- One Slack event creates at most one draft update.
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
    "source_label": "#channel-name",
    "source_url": "https://slack.com/app_redirect?channel=C123",
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
`Source: #channel-name` with the channel name embedded as the Slack link.

## Golden Examples

### Create update: timeline/progress message

Input: `Microsoft confirmed the Copilot enablement pilot is moving to September.
We have 3 validation tasks left before partner readout.`

Expected summary lines:

- Microsoft confirmed the Copilot enablement pilot is moving to September.
- 3 validation tasks remain before partner readout.

### Create update: blocker/action message

Input: `AWS Graviton benchmark review is blocked until the platform logs are
attached. Sameer will follow up by Aug 15.`

Expected summary lines:

- AWS Graviton benchmark review is blocked until platform logs are attached.
- Sameer will follow up by Aug 15.

### Ignore: acknowledgement only

Input: `Thanks, sounds good.`

Expected decision: ignore.

### Ignore: channel noise

Input: joined-channel or emoji/reaction-only event.

Expected decision: ignore.

### Borderline create: informal ask

Input: `Can someone check if this changes the SAP timeline? Not sure yet.`

Expected decision: create only if linked or thread context contains grounded
timeline facts; otherwise ignore or flag `needs_human_attention=true`.
