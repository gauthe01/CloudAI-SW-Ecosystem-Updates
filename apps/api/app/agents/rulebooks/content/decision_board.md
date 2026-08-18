---
name: decision_board
version: active-2026-08-18-interview-v1
status: active
owner: developer
---

# Decision Board Rulebook

## Purpose

Generate a presenter Decision Board for the selected partner scope and period.

The board is a leadership attention and risk/action surface. It should show the
items that may need leadership to know, decide, unblock, track, or monitor. It
is not a general summary, a highlights board, or a replacement for the Approved
Updates list.

## Input Contract

The agent receives:

- Selected reporting scope: cycle, optional date range, selected partner IDs,
  and whether the scope is all partners or a selected subset.
- Approved partner updates only. Topic-level updates are not Decision Board
  inputs.
- Same-period partner metadata for the selected partners:
  - partner health/status
  - metadata risk rows with description, severity, due date, green action, and
    ramification
- This rulebook and output contract.

The agent must not use pending updates, dismissed updates, draft updates,
topic-level updates, raw source payloads, connected-source raw events,
resource-library links, outside knowledge, model memory, or assumptions.

## Card Eligibility

Create cards for risks, actions, and watch items.

An approved update can create a card when semantic analysis of that update text
shows a blocker, risk, decision needed, owner ask, dependency, deadline,
escalation, concrete next action, or watch item. Positive opportunities can
create cards only when they include a decision, ask, deadline, or action.

Partner metadata risk rows can create cards when their severity is not green or
low. Green and low metadata risks should be excluded from the board.

Partner health/status alone never creates a card and never raises priority. In
this product, red status means engagement/relevance has dropped; it does not
mean urgent escalation.

## Approved Update Card Rules

- The decision to show an approved update on the board must be based solely on
  semantic analysis of that approved update's text.
- One approved update can create at most one card.
- If one approved update contains multiple signals, show those signals in the
  single card.
- The title is generated from the strongest signal in the update line. Aim for
  5-10 words.
- Do not include the partner name in the title unless it is needed for meaning;
  the UI shows partner name separately.
- The update line must be one natural line that stays very close to the approved
  update wording.
- If the approved update has bullets or HTML formatting, combine only the
  relevant signal-bearing text into one natural line.
- Preserve grounded facts, numbers, dates, owners if already in the text,
  qualifiers, status wording, and business terms.
- The action field is optional. Include it only when the update explicitly or
  semantically contains a grounded action, request, ask, question needing
  follow-up, pending input, unresolved dependency, approval needed, next step,
  due/follow-up wording, or action-item language.
- If no action is grounded in the update text, omit the action field. Do not say
  that no action was mentioned.
- Do not invent new actions, impacts, owners, due dates, severity, or business
  consequences.

## Metadata Risk Card Rules

- One metadata risk row can create at most one card.
- Include metadata risks with severity values such as amber, medium, red, high,
  or critical.
- Exclude metadata risks with severity values green or low.
- If severity is unclear but the risk text semantically looks important, include
  it as P3.
- The title is a 5-10 word summary of the strongest risk signal and should not
  include the partner name unless needed for meaning.
- The update line should combine description, severity, due date, and
  ramification into one natural grounded line.
- Do not include assigned owner in the card.
- Do not include green action in the update line.
- The action field is optional. If green_action is present, use it as the action
  with light cleanup only. Do not reinterpret or expand it.
- If green_action is missing, omit the action field.

## Priority Rules

Every card must be assigned one priority lane: P1, P2, or P3.

For approved-update-derived cards, assign priority semantically from the update
text:

- `P1`: blocker, critical risk, urgent deadline, executive/customer-impacting
  issue, high-severity issue, or urgent leadership attention.
- `P2`: decision needed, dependency, owner follow-up, non-critical deadline,
  concrete action, or important follow-up.
- `P3`: watch item, lower-urgency concern, monitor-only item, or anything that
  might need monitoring but is not P1 or P2.

For metadata-risk cards, use direct severity mapping:

- `red`, `high`, `critical` -> `P1`
- `amber`, `medium` -> `P2`
- `green`, `low` -> exclude
- unclear severity -> include only if semantically important, default `P3`

Partner health/status is only a tie-breaker when otherwise similar cards must
be ordered or selected. Tie-breaker order is green first, then amber, then red.
Status does not create a card and does not raise priority.

## Dedupe And Selection Rules

- Return no more than 15 cards.
- Generate fewer than 15 when fewer items are necessary.
- Do not merge approved-update cards with metadata-risk cards, even if they
  describe a related issue. Show both so the presenter can decide.
- Deduplicate semantically similar approved-update cards with each other.
- Deduplicate semantically similar metadata-risk cards with each other.
- When more than 15 candidate cards exist, keep cards by priority first, then by
  strongest semantic signal.
- Stronger signals include explicit blockers, explicit decisions or asks, urgent
  deadlines, high/critical severity, customer or executive impact, and concrete
  actions.
- Drop weaker P3 watch items first when the board exceeds 15 cards.

## UI-Facing Card Shape

Cards have only these visible content elements:

- Partner name, supplied separately as `partner_name`
- Title
- Update line
- Action, only when explicitly grounded

Do not produce visible rationale, source text, owner fields, separate severity
fields, or separate due-date fields. Severity and due date may appear inside the
metadata risk update line when grounded by metadata. Approved update text may
contain an owner or due date if it was already part of the approved update line.

Hidden traceability fields are allowed for backend audit and debugging, such as
source kind, approved update ID, and metadata risk ID. These fields are not
visible Decision Board card content.

## Output Contract

Return one JSON object only:

```json
{
  "signals": [
    {
      "partner_id": "uuid",
      "partner_name": "Partner name",
      "priority": "P1|P2|P3",
      "title": "5-10 word signal title",
      "update_line": "One natural grounded line",
      "action": "Only when explicitly grounded",
      "source_kind": "approved_update|metadata_risk",
      "update_id": "uuid when source_kind is approved_update",
      "metadata_risk_id": "uuid when source_kind is metadata_risk"
    }
  ],
  "source_note": "Optional short note about scope/data availability"
}
```

Required per signal:

- `partner_id`
- `partner_name`
- `priority`
- `title`
- `update_line`
- `source_kind`

Optional per signal:

- `action`
- `update_id`
- `metadata_risk_id`

Use `source_note` when no cards are found:

`No Decision Board items found for the selected partners and period.`

## Golden Examples

### Approved update creates P3 watch card

Approved update:

- Partner: SAP HANA Cloud
- Update text: `ARM64 image publishing automation for SAP HANA Cloud test
  artifacts needs monitoring after the implementation was accepted as a partner
  demo acceleration item.`

Expected card:

- Partner name: `SAP HANA Cloud`
- Priority: `P3`
- Title: `ARM64 publishing automation monitoring`
- Update line: `ARM64 image publishing automation for SAP HANA Cloud test
  artifacts needs monitoring after the implementation was accepted as a partner
  demo acceleration item.`
- Action: omit, unless the source text explicitly gives one

### Approved update with explicit action

Approved update:

- Partner: AWS
- Update text: `Release validation is blocked until the security exception is
  approved. Security review is due Aug. 22.`

Expected card:

- Priority: `P1`
- Title: `Security exception blocks release validation`
- Update line: `Release validation is blocked until the security exception is
  approved, and security review is due Aug. 22.`
- Action: `Security exception approval is needed`

Do not invent a broader action such as `Escalate to leadership`.

### Metadata risk with green action

Metadata risk:

- Partner: Microsoft
- Description: `Launch messaging dependency`
- Severity: `amber`
- Due date: `September`
- Green action: `Confirm campaign input owner`
- Ramification: `Could delay Q4 campaign review.`

Expected card:

- Priority: `P2`
- Title: `Launch messaging dependency`
- Update line: `Launch messaging dependency is marked amber, due in September,
  and could delay Q4 campaign review.`
- Action: `Confirm campaign input owner`

### Metadata risk without action

Metadata risk:

- Partner: AWS
- Description: `Legal agreement delay`
- Severity: `high`
- Due date: `Aug. 22`
- Green action: empty
- Ramification: `Could delay launch messaging.`

Expected card:

- Priority: `P1`
- Title: `Legal agreement delay`
- Update line: `Legal agreement delay is marked high, due Aug. 22, and could
  delay launch messaging.`
- Action: omit

### Ignore ordinary progress

Approved update:

- Partner: Cohere
- Update text: `Partner milestone remains on track and the team completed the
  weekly sync.`

Expected output:

- No card.

Reason:

- The update has ordinary progress but no action, risk, blocker, decision,
  dependency, deadline, escalation, or watch item.
