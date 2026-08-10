# Feature 23B - Rulebook Business Interview

## Purpose

Feature 23B is the product-and-engineering interview gate for the first real
developer-owned agent rulebook in Cloud AI Software Ecosystem Updates.

Feature 23 created the technical rulebook framework. Feature 23B decides what
the first production rulebook should actually say before any model-backed
extraction is implemented.

This feature exists to prevent vague prompts, accidental business assumptions,
and code-level AI behavior that cannot be explained to a contributor,
presenter, admin, or technical reviewer.

## Why This Is A Separate Feature

The app is intended to be agentic, but agentic behavior must still be governed
by explicit product rules:

- What source events count as meaningful updates.
- What source events must be ignored.
- What language a draft update should use.
- What fields the model must return.
- What confidence or review flags are needed.
- What evidence can be stored for technical traceability.
- What the contributor sees before approving an update.

Without this feature, Feature 24 would be only "call OpenAI and hope the prompt
works." That is not production-shaped enough for this product.

## Scope

Feature 23B is documentation and decision capture only.

It does not:

- Call the enterprise OpenAI-compatible endpoint.
- Change the database schema.
- Create or modify pending updates.
- Add a user-facing rulebook editor.
- Replace the placeholder markdown rulebooks yet.

It does:

- Select the first source rulebook to finalize.
- Interview the product owner one question at a time.
- Convert the answers into a clear rulebook decision pack.
- Identify any UI implications before implementation.
- Define test examples that later prove the agent behavior is correct.

## Recommended First Rulebook

Start with `source_event.jira` unless the product owner chooses otherwise.

Reasoning:

- Jira is more structured than Slack.
- The product already expects single-ticket connected sources.
- Ticket-level source boundaries make approval, traceability, and test cases
  easier.
- It is the safest first place to prove model-backed extraction before moving
  to broader Slack or document sources.

Alternative first rulebooks:

- `source_event.slack`
- `source_event.sharepoint`
- `source_event.confluence`
- `source_event.github`
- `update_quality`
- `presenter_intelligence`
- `executive_email`
- `decision_board`

## Interview Structure

The interview should happen one question at a time. The product owner should
choose from options where useful, with room to override the options in free
text.

### 1. Rulebook Selection

Decide which rulebook is finalized first.

Output:

- Selected rulebook name.
- Reason for choosing it first.
- Any sources explicitly deferred.

### 2. Source Event Scope

Define which source events the agent is allowed to process.

For Jira, this may include:

- Issue created.
- Issue status changed.
- Comment added.
- Assignee changed.
- Due date or target date changed.
- Priority or severity changed.
- Linked issue changed.
- Attachment or document reference added.

Output:

- Allowed event types.
- Event types to ignore.
- Whether one source event can create multiple draft updates.

### 3. Meaningful Update Rules

Define what makes an event worthy of a contributor-reviewable draft update.

Candidate signal categories:

- Status/progress change.
- New blocker, risk, or issue.
- Milestone/date change.
- Decision or leadership ask.
- Scope change.
- Ownership/action change.
- Dependency change.
- Customer/partner impact.
- New evidence that changes the monthly narrative.

Output:

- Must-capture categories.
- Nice-to-capture categories.
- Ignore categories.

### 4. Ignore Rules

Define what the agent should suppress.

Examples:

- Formatting-only changes.
- Duplicate comments.
- Thank-you or acknowledgement messages.
- Bot-generated noise.
- Internal system metadata with no business meaning.
- Events outside the connected source scope.

Output:

- Explicit ignore list.
- Rules for borderline cases.
- Whether broad capture is preferred over aggressive filtering.

### 5. Draft Update Language

Define the writing style of generated draft updates.

Questions to resolve:

- Should language be factual, executive, operational, or neutral?
- Should the update mention the source tool name?
- Should it include partner name?
- Should it avoid speculation?
- Should it preserve uncertainty when the source is unclear?
- Should it be one sentence or a short paragraph?

Output:

- Tone rules.
- Required phrasing rules.
- Banned phrasing.
- Example good and bad updates.

### 6. Output Data Contract

Define what the model must return to the backend.

Minimum proposed fields:

- `should_create_update`
- `draft_update_text`
- `source_summary`
- `reasoning_category`
- `confidence`
- `needs_human_attention`
- `dedupe_key_hint`
- `event_importance`
- `rulebook_trace`

Output:

- Approved JSON fields.
- Required vs optional fields.
- Validation rules.

### 7. Contributor Review Behavior

Define what the contributor should see.

The current product decision is that all generated updates go to contributor
review first. Feature 23B should confirm whether the contributor needs any
extra indicators, such as:

- Source type badge.
- Confidence flag.
- Needs attention flag.
- Suggested reason/category.
- Original source link.

Output:

- UI display requirements.
- Anything explicitly hidden from UI and kept only for technical processing.

### 8. Dedupe And Conflict Rules

Define how duplicate or similar source events behave.

Current product direction:

- Exact duplication can be rejected automatically.
- Slightly different updates should be kept broad and left for contributor
  review.
- One update comes from one source event only.

Output:

- Dedupe strategy.
- Similarity threshold behavior.
- How conflicts are surfaced.

### 9. Traceability And Retention

Define what evidence is retained for technical processing.

The product direction so far:

- Retain only what is needed for technical processing.
- Do not show raw technical payloads in normal UI.
- Contributors do not need source excerpts in the current UI.

Output:

- Stored payload summary.
- Source link behavior.
- Audit trace requirements.

### 10. Golden Test Examples

Collect representative source-event examples before implementation.

Each example should include:

- Source event type.
- Input summary.
- Expected decision: create or ignore.
- Expected draft update text or reason ignored.
- Expected flags.

Output:

- At least five examples for the chosen first rulebook.
- At least two ignore examples.
- At least one borderline example.

## UI Requirements

Feature 23B itself has no new UI.

However, the interview can produce UI requirements for later features. These
must be recorded before Feature 24 starts.

Possible UI implications:

- Pending Updates may need a confidence or attention indicator.
- Edit flow may need to preserve AI-generated draft text after contributor
  edits.
- Connected Sources may need clearer source-scope guidance before request
  submission.
- Admin approval may need access-test notes for model-backed extraction.

## Backend Requirements

Feature 23B does not change backend runtime behavior.

It produces the decision inputs needed by later backend features:

- First real markdown rulebook content.
- Agent input contract.
- Agent output contract.
- Validation rules.
- Test cases for model-backed extraction.

## AWS / Deployment Impact

Feature 23B has no direct AWS runtime impact.

The decisions from this feature affect future deployments because finalized
rulebooks will be packaged into the API and worker image. In AWS:

- The API and worker will load the same rulebook version from the backend image.
- The worker will use the rulebook during source-event processing.
- The enterprise OpenAI-compatible endpoint credentials will still come from
  AWS Secrets Manager or SSM, not from rulebook files.
- `agent_runs` will record the rulebook trace version used for each model-backed
  extraction.

## Acceptance Criteria

Feature 23B is complete when:

- The first rulebook to finalize is chosen.
- The product owner has answered the interview questions for that rulebook.
- A decision pack exists with event scope, extraction rules, ignore rules,
  language rules, output contract, dedupe rules, traceability rules, and golden
  test examples.
- Any UI implications are documented.
- The product owner explicitly approves moving into the implementation feature
  that replaces the placeholder rulebook content.

## Next Feature

After Feature 23B, the next feature should be:

- Feature 23C - First Production Rulebook Content, if we want to update the
  markdown rulebook before wiring OpenAI.
- Feature 24 - Model-Backed Source Event Extraction, if Feature 23C is folded
  into the extraction implementation.

The safer path is Feature 23C first.
