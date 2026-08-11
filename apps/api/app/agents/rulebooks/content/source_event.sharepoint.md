---
name: source_event.sharepoint
version: production-2026-08-11
status: production
owner: developer
---

# SharePoint Source Event Extraction Rulebook

## Purpose

Convert approved SharePoint file events and extracted file content into
contributor-reviewable draft updates for Cloud AI Software Ecosystem Updates.

The agent must create updates only from readable, grounded file content or
approved file metadata that changes partner readiness, progress, risk, timeline,
dependency, action, priority, evidence, or partner impact.

All generated updates enter Pending Updates first. Nothing is approved
automatically.

## Input Contract

The agent receives one approved SharePoint file source event at a time with:

- Partner and connected-source identity.
- SharePoint file source URL.
- File title/name, file metadata, event type, and event timestamp.
- Extracted readable file content when available.
- Retained payload and storage references.
- Approved connected-source metadata.
- Idempotency key and source event ID.

Use only extracted readable file content and approved file metadata. If file
extraction is partial or failed, do not invent around it.

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
- The file source item's own timestamp determines the update month. A document
  revision from April creates an April update, and a revision from July creates
  a July update, even if both are fetched during a later month.
- Do not repeat prior-month file facts in a later month just because a later
  fetch included older revisions as context. Older revisions may provide context
  for dedupe and grounding, but the created update must be based only on the
  source item for that month.
- Extract only net-new facts introduced or changed by the current file source
  item. Do not repeat same-month facts from earlier file revisions when the
  current revision merely carries forward, references, or summarizes them.
- If a file revision repeats earlier context and adds one new grounded fact,
  create a draft with only the new fact or facts. If it adds no net-new fact,
  ignore it.
- Acknowledgements or carried-forward notes such as "helpful", "noted",
  "confirmed", or similar wording are not new facts unless they change status,
  timeline, commitment, priority, risk, dependency, owner, or next action.
- Remove document boilerplate when it adds no business meaning.

## Allowed SharePoint / Files Events

Process only these events:

- Approved connected SharePoint file is created or added.
- Approved connected SharePoint file is updated.
- File title or name changes only if the change affects business meaning.
- New version is available and readable.
- File contains changed facts about progress, blockers, timelines, priorities,
  dependencies, actions, or partner impact.

## Extraction Rules

Create a draft update when the file event or extracted file content adds or
changes a grounded fact in one or more of these categories:

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

Ignore SharePoint events when they do not affect status, risk, timeline,
dependency, action, priority, severity, evidence, or partner impact.

Always ignore:

- File permission-only changes.
- File moved or renamed with no business meaning.
- Metadata-only change with no content change.
- Empty or unreadable file.
- Unsupported file type.
- Duplicate file version with no extracted text or content change.
- Formatting-only document edits.

## Dedupe And Conflict Rules

- Exact duplicate file events must not create duplicate Pending Updates.
- Webhook redelivery must be ignored by idempotency key.
- If two file versions say essentially the same thing, keep only the first draft
  unless the later version adds new facts.
- If a later file version updates or corrects a previous fact, create a new
  Pending Update instead of silently editing the old one.
- One file event creates at most one draft update.
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
    "source_label": "File Title",
    "source_url": "https://sharepoint.example.com/file",
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
`Source: File Title` with the title embedded as the SharePoint file link.

## Golden Examples

### Create update: planning deck timeline changed

Input: approved SharePoint deck says `Initial partner benchmark readout moves
from August to September; 4 validation items remain open.`

Expected summary lines:

- Initial partner benchmark readout moved from August to September.
- 4 validation items remain open.

### Create update: new blocker in document

Input: approved file says `Arm64 image publishing is blocked pending security
review sign-off.`

Expected summary line:

- Arm64 image publishing is blocked pending security review sign-off.

### Ignore: formatting-only document change

Input: same document content, only slide formatting or template changed.

Expected decision: ignore.

### Ignore: unreadable or unsupported file

Input: file cannot be extracted or no readable text is available.

Expected decision: ignore with no invented summary.

### Borderline create: vague new section

Input: document adds `partner readiness risk under review` but gives no owner,
date, or impact.

Expected summary line:

- Partner readiness risk is under review.

Expected flags: `needs_human_attention=true`.
