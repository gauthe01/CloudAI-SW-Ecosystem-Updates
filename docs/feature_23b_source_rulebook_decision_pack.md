# Feature 23B - Source Rulebook Decision Pack

## Status

Approved for Feature 23B decision capture.

This document records the business rules for the first production source-event
rulebooks. It is documentation only. Feature 23C will convert these decisions
into production rulebook markdown under `apps/api/app/agents/rulebooks/content`.

## Source Rulebooks Covered

- `source_event.jira`
- `source_event.slack`
- `source_event.sharepoint`
- `source_event.confluence`
- `source_event.github`

## Shared Rules For All Source Types

Generated draft updates must be grounded in actual source facts.

- The agent must not invent facts, owners, dates, blockers, partner impact,
  decisions, risks, quantities, or status claims.
- The agent may rewrite, clean, and compress source wording, but every factual
  claim must be grounded in source content, source metadata, linked evidence, or
  approved connected-source metadata.
- If the available source material is not enough to support a factual update,
  the agent must ignore the event or flag the draft internally for human
  attention.
- Draft updates should be bulleted, not paragraph style.
- Each bullet should contain one grounded fact.
- Do not join update clauses with semicolons. If a semicolon would be needed,
  split the content into separate bullet points instead.
- Relevant quantitative information must be preserved, including numbers,
  counts, dates, months, time ranges, percentages, quantities, priority labels,
  severity labels, version numbers, estimates, and benchmark values.
- Relevant links found in source items must be preserved in the extracted
  update line they support, similar to quantitative details. Do not drop a
  source-item link when the linked reference is part of the grounded update.
- The source item's own timestamp determines the update month. If Jira comments,
  Slack messages, file revisions, Confluence edits, or GitHub events come from
  different months, their extracted updates must be created in those source-item
  months, not in the month when the agent fetched or processed them.
- Do not repeat prior-month facts in a later month just because the later fetch
  included older source items as context. Older source items may provide context
  for dedupe and grounding, but the created update must be based only on the
  source item for that month.
- Extract only net-new facts introduced or changed by the current source item.
  Do not repeat same-month facts from earlier source items when the current item
  merely acknowledges, references, carries forward, or summarizes them.
- If a source item repeats earlier context and adds one new grounded fact,
  create a draft with only the new fact or facts. If it adds no net-new fact,
  ignore it.
- Acknowledgements such as "helpful", "noted", "thanks", "confirmed", or similar
  wording are not new facts unless they change status, timeline, commitment,
  priority, risk, dependency, owner, or next action.
- Do not extract facts from acknowledgement clauses such as "the X estimate is
  helpful" or "noted on X"; those clauses refer to earlier information and are
  not net-new source facts.
- Conversational noise should be removed, including greetings, thanks,
  apologies, sign-offs, vacations, and acknowledgements when they add no
  business meaning.
- All generated updates enter Pending Updates for contributor review first.
- No generated update is approved automatically.

## Shared Meaningful Update Rules

Create a draft update when a source event adds or changes a grounded fact in one
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

Ignore source events when they do not affect status, risk, timeline, dependency,
action, priority, severity, evidence, or partner impact.

## Shared Output Contract

Mandatory fields:

- `decision`: `create_update` or `ignore`.
- `source_summary`: factual summary of what the source event contained.
- `reasoning_category`: blocker, timeline, progress, dependency, priority,
  evidence, partner impact, ownership, or other approved category.
- `confidence`: model confidence for audit and validation.
- `needs_human_attention`: boolean.
- `rulebook_trace`: rulebook name and version used.

Mandatory only when `decision = create_update`:

- `draft_update.summary_lines`: bulleted Pending Update text.
- `draft_update.cycle_month`: first day of the month from the source item's own
  timestamp.
- `dedupe_key_hint`: stable hint to help avoid duplicate drafts.
- `event_importance`: low, medium, or high.

Optional and audit-only:

- `draft_update.title`.
- `grounding_notes`.

## Shared Contributor Review Behavior

Contributor-facing Pending Updates should remain simple.

- Show source badge and generated bulleted update text.
- On row click, show only `Source: Link Title`, with the link embedded in the
  title text.
- Do not show raw source payloads in normal contributor UI.
- Do not show model reasoning in normal contributor UI.
- Do not show confidence in normal contributor UI.
- Keep `needs_human_attention` in backend/audit metadata unless a later UI
  decision explicitly exposes it.

## Shared Dedupe And Conflict Rules

- Exact duplicate source events must not create duplicate Pending Updates.
- Webhook redelivery must be ignored by idempotency key.
- If two different events say essentially the same thing, keep only the first
  draft unless the later event adds new facts.
- When a later event adds new facts while repeating previous facts, the later
  draft must include only the net-new or changed facts.
- If a later event updates or corrects a previous fact, create a new Pending
  Update instead of silently editing the old one.
- One source event creates at most one draft update.
- If uncertain whether an event is duplicate or new, create a draft and let the
  contributor decide.

## Shared Traceability And Retention Rules

Store enough information for audit and debugging:

- Source type.
- Source link.
- Link title.
- Event type.
- Event timestamp.
- Connected source ID.
- Source event ID.
- Idempotency key.
- Rulebook name and version.
- Model name.
- Model decision.
- Validation result.
- Model output JSON in `agent_runs`.

Do not expose raw payloads, full source comments, or model reasoning in normal
contributor UI.

## Jira Rulebook Decisions

Rulebook: `source_event.jira`

Allowed events:

- Issue created.
- Status changed.
- Comment added.
- Due date or target month changed.
- Priority or severity changed.
- Linked issue or dependency changed.
- Attachment or document reference added.

Excluded from initial scope:

- Assignee or owner changed.

Jira-specific ignore rules:

- Formatting-only edits.
- Duplicate comments or repeated status with no new information.
- Thank-you or acknowledgement comments.
- Bot-generated or automation-only Jira noise.
- Label, tag, watch, or vote changes with no business meaning.
- Events outside the approved connected Jira issue scope.
- Assignee or owner changes.
- Chatter that does not affect status, risk, timeline, dependency, action, or
  partner impact.

Jira request/comment handling:

- Do not ignore a Jira comment solely because it is phrased as a request or
  question. If the comment explicitly asks for target dates, shareable-version
  timing, blockers, gaps, dependencies, SAP-facing inputs, priority, severity,
  review, evidence, or next actions, create a grounded draft from that request.
- The request itself is the grounded fact. Do not invent the answer or final
  date.
- Set `needs_human_attention=true` when the request needs contributor review.

Jira update style:

- Line-by-line update text.
- Clean monthly progress-summary style.
- Preserve approximate timing exactly when grounded, such as `~6 weeks` or
  `Aug./Sept.`
- Names may be used only when ownership or action is relevant and explicitly
  grounded.
- Do not add invented uncertainty phrasing such as "needs confirmation."

Jira source reveal:

- `Source: Jira Link Title`, with the title embedded as the Jira link.

Jira golden examples:

1. Create update: July progress comment.
   - Input: comment says initial full repository expected in `~6 weeks`,
     incremental versions available sooner, no major blockers, help needed
     finding an SVE expert, SAP AGI CPU evaluation in progress with possible CRB
     in Aug./Sept.
   - Expected lines:
     - Initial full repository of learning material expected in ~6 weeks, with
       incremental versions available sooner.
     - No major blockers identified.
     - Assistance needed to find an SVE expert for deeper review.
     - SAP's AGI CPU evaluation is in progress, with a potential CRB delivery in
       Aug./Sept.
2. Create update: course scoping progress.
   - Input: draft scoping document is available/shared, next steps involve
     proposing course material based on SAP feedback.
   - Expected lines:
     - Draft scoping document for the training course is available for review.
     - Next steps involve proposing course material based on SAP feedback.
3. Create update: follow-up comment with repeated acknowledgements.
   - Input: later comment says the `~6-week estimate` is helpful, says ATG
     support is noted, and then adds that SAP AGI CPU evaluation is starting,
     legal teams are working through equipment loan and collaboration
     agreements, SAP may receive a CRB in Aug./Sept., and `(4) QS A1 systems`
     are planned for performance benchmarking in October.
   - Expected line:
     - SAP's AGI CPU evaluation is starting while legal teams work through
       equipment loan and collaboration agreements; current timeline may provide
       SAP with a CRB in Aug./Sept. and 4 QS A1 systems for performance
       benchmarking in October.
   - Do not extract the `~6-week estimate` or ATG support facts from this source
     item because they appear only as acknowledgements of earlier comments.
4. Ignore: thank-you only.
   - Input: "Thanks for the update, no worries on the delay."
   - Expected decision: ignore.
5. Ignore: formatting/edit only.
   - Input: Jira description formatting changed, no field or factual meaning
     changed.
   - Expected decision: ignore.
6. Borderline create: action request without firm date.
   - Input: comment asks for target date, blockers/gaps, and whether priority
     should change due to SAP / AGI CPU impact.
   - Expected line:
     - Target date, blockers, SAP-facing input needs, and priority should be
       reviewed for the course material.
   - Expected flags: `needs_human_attention=true`.

## Slack Rulebook Decisions

Rulebook: `source_event.slack`

Allowed events:

- New message in an approved connected channel.
- Thread reply in an approved connected channel.
- Edited message only if the edit adds or changes business facts.
- Shared link or file reference when the message text gives enough grounded
  context.

Slack-specific ignore rules:

- Emoji or reaction-only events.
- Joins, leaves, and channel admin messages.
- Bot or system messages.
- Thank-you or acknowledgement-only messages.
- Deleted messages.
- Formatting-only edits.
- Messages outside the approved connected channel.

Slack source reveal:

- `Source: #channel-name`, with the channel name embedded as the Slack link.

Slack golden examples:

1. Create update: timeline/progress message.
   - Input: "Microsoft confirmed the Copilot enablement pilot is moving to
     September. We have 3 validation tasks left before partner readout."
   - Expected lines:
     - Microsoft confirmed the Copilot enablement pilot is moving to September.
     - 3 validation tasks remain before partner readout.
2. Create update: blocker/action message.
   - Input: "AWS Graviton benchmark review is blocked until the platform logs
     are attached. Sameer will follow up by Aug 15."
   - Expected lines:
     - AWS Graviton benchmark review is blocked until platform logs are
       attached.
     - Sameer will follow up by Aug 15.
3. Ignore: acknowledgement only.
   - Input: "Thanks, sounds good."
   - Expected decision: ignore.
4. Ignore: channel noise.
   - Input: joined-channel or emoji/reaction-only event.
   - Expected decision: ignore.
5. Borderline create: informal ask.
   - Input: "Can someone check if this changes the SAP timeline? Not sure yet."
   - Expected decision: create only if linked or thread context contains
     grounded timeline facts; otherwise ignore or flag
     `needs_human_attention=true`.

## SharePoint / Files Rulebook Decisions

Rulebook: `source_event.sharepoint`

Allowed events:

- Approved connected SharePoint file is created or added.
- Approved connected SharePoint file is updated.
- File title or name changes only if the change affects business meaning.
- New version is available and readable.
- File contains changed facts about progress, blockers, timelines, priorities,
  dependencies, actions, or partner impact.

SharePoint / Files-specific ignore rules:

- File permission-only changes.
- File moved or renamed with no business meaning.
- Metadata-only change with no content change.
- Empty or unreadable file.
- Unsupported file type.
- Duplicate file version with no extracted text or content change.
- Formatting-only document edits.

SharePoint / Files source reveal:

- `Source: File Title`, with the file title embedded as the file link.

SharePoint / Files extraction rule:

- Use only extracted readable file content and approved file metadata.
- If file extraction is partial or failed, do not invent around it.

SharePoint / Files golden examples:

1. Create update: planning deck timeline changed.
   - Input: approved SharePoint deck says "Initial partner benchmark readout
     moves from August to September; 4 validation items remain open."
   - Expected lines:
     - Initial partner benchmark readout moved from August to September.
     - 4 validation items remain open.
2. Create update: new blocker in document.
   - Input: approved file says "Arm64 image publishing is blocked pending
     security review sign-off."
   - Expected line:
     - Arm64 image publishing is blocked pending security review sign-off.
3. Ignore: formatting-only document change.
   - Input: same document content, only slide formatting or template changed.
   - Expected decision: ignore.
4. Ignore: unreadable or unsupported file.
   - Input: file cannot be extracted or no readable text is available.
   - Expected decision: ignore with no invented summary.
5. Borderline create: vague new section.
   - Input: document adds "partner readiness risk under review" but gives no
     owner, date, or impact.
   - Expected line:
     - Partner readiness risk is under review.
   - Expected flags: `needs_human_attention=true`.

## Confluence Rulebook Decisions

Rulebook: `source_event.confluence`

Allowed events:

- Approved connected Confluence page is created.
- Approved connected Confluence page is updated.
- Page comment added, only if comments are in connected-source scope.
- Page title changes only if the change affects business meaning.
- Page content changes that include progress, blocker, timeline, priority,
  dependency, action, evidence, or partner impact.

Confluence-specific ignore rules:

- Permission-only changes.
- Watch, like, or reaction changes.
- Label-only changes unless the label changes business status or severity.
- Page moved with no content or business meaning.
- Formatting-only edits.
- Duplicate page update with no extracted content change.
- Events outside the approved connected page scope.

Confluence source reveal:

- `Source: Page Title`, with the page title embedded as the Confluence link.

Confluence golden examples:

1. Create update: page progress change.
   - Input: page says "Elastic vector search validation completed; next
     benchmark review scheduled for October."
   - Expected lines:
     - Elastic vector search validation completed.
     - Next benchmark review is scheduled for October.
2. Create update: dependency added.
   - Input: page update adds "Delivery depends on access to partner test
     environment by Sep 10."
   - Expected line:
     - Delivery depends on access to the partner test environment by Sep 10.
3. Ignore: label-only change.
   - Input: label added or removed with no content or business status change.
   - Expected decision: ignore.
4. Ignore: formatting-only page edit.
   - Input: headings or table formatting changed, same facts.
   - Expected decision: ignore.
5. Borderline create: page says priority is being reviewed.
   - Input: "Priority is being reviewed after partner planning discussion," with
     no final outcome.
   - Expected line:
     - Priority is being reviewed after the partner planning discussion.
   - Expected flags: `needs_human_attention=true`.

## GitHub Rulebook Decisions

Rulebook: `source_event.github`

Allowed events:

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

GitHub-specific ignore rules:

- Star, fork, or watch events.
- Pure CI/check noise unless it indicates a meaningful blocker or readiness
  change.
- Formatting-only edits.
- Bot-only dependency noise with no partner impact.
- Label churn with no business meaning.
- Branch pushes unless tied to an approved issue, pull request, or release
  signal.
- Events outside the approved repository, issue, or pull request scope.

GitHub source reveal:

- `Source: GitHub Link Title`, with the title embedded as the GitHub link.

GitHub quantitative preservation:

- Preserve PR numbers, issue numbers, release versions, dates, counts, error
  names, and benchmark numbers when relevant.

GitHub golden examples:

1. Create update: issue blocker.
   - Input: issue says "ARM64 publishing is blocked by failing container signing
     workflow."
   - Expected line:
     - ARM64 publishing is blocked by the failing container signing workflow.
2. Create update: PR merged.
   - Input: PR `#118` merged and description says it automates ARM64 image
     publishing for SAP HANA Cloud test artifacts.
   - Expected line:
     - PR #118 automated ARM64 image publishing for SAP HANA Cloud test
       artifacts.
3. Create update: release/version.
   - Input: release `v2.4.0` published with Graviton benchmark support and 3
     known validation gaps.
   - Expected lines:
     - Release v2.4.0 includes Graviton benchmark support.
     - 3 validation gaps remain.
4. Ignore: star/watch/fork.
   - Input: repository starred or watched.
   - Expected decision: ignore.
5. Ignore: CI noise.
   - Input: CI job failed and retried, but no issue, PR, or release text
     indicates partner impact or readiness change.
   - Expected decision: ignore.
6. Borderline create: dependency bot PR.
   - Input: dependency bot opens PR to update a library, but no connected issue
     or partner impact is stated.
   - Expected decision: ignore unless linked context shows partner impact; if
     uncertain, flag `needs_human_attention=true`.

## Feature 23B Completion Criteria

Feature 23B is complete for source-event extraction when this decision pack is
approved and Feature 23C can safely convert the decisions into production
rulebook markdown files.
