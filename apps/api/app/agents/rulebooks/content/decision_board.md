---
name: decision_board
version: placeholder-2026-08-11
status: placeholder
owner: developer
---

# Decision Board Rulebook

## Purpose

Generate presenter decision-board cards from approved updates for the selected
partner scope and reporting period. The board should help the presenter see
what needs a decision, owner action, leadership attention, or monitoring.

## Input Contract

The agent receives:

- Selected reporting scope: cycle, optional date range, and selected partner IDs.
- Approved updates only, including partner name, update title, approved summary,
  source type, source label, source URL, and approval timestamp.
- This rulebook and output contract.

The agent must not use pending updates, dismissed updates, partner metadata,
connected-source raw events, resource-library links, outside knowledge, or model
memory.

## Analysis Rules

- Use only facts present in the approved update text and supplied source fields.
- Create a card only when the approved update contains a decision-worthy signal:
  explicit next action, blocker, owner ask, deadline, readiness risk, dependency,
  escalation, approval, or status change that requires presenter attention.
- Do not invent owners, dates, priorities, blockers, rationale, or next steps.
- Preserve all quantitative facts that appear in the approved update.
- Preserve relevant links. If a link is present in the approved update or source
  fields, carry the link into the same decision card using `source_label` and
  `source_url`.
- Do not repeat the same signal as multiple cards. Merge only when the facts
  clearly describe the same action for the same partner.
- Do not use semicolons. If two distinct facts would need a semicolon, separate
  them into another sentence or another card.
- Assign priority only from grounded urgency:
  - `P1`: confirmed blocker, high-severity risk, urgent owner ask, or dated item
    that threatens the reporting cycle.
  - `P2`: clear action, dependency, or follow-up that should be tracked but is
    not an immediate blocker.
  - `P3`: watch item, positive movement that still needs monitoring, or lower
    urgency follow-up.
- If urgency is unclear, use `P3` or leave optional severity fields blank rather
  than exaggerating.

## Ignore Rules

- Ignore general background, compliments, and narrative context that does not
  create an action, decision, blocker, dependency, risk, or watch item.
- Ignore facts that are already outside the selected approved-update scope.
- Ignore any idea that requires synthesis beyond the approved update text.
- If no approved update contains a decision-board-worthy signal, return no
  cards.

## Output Contract

Return JSON with:

```json
{
  "signals": [
    {
      "partner_id": "uuid if supplied",
      "partner_name": "Partner name",
      "priority": "P1, P2, or P3",
      "title": "Short decision-card title",
      "action": "The action, decision, ask, or watch item",
      "rationale": "Why this belongs on the decision board, grounded in the approved update",
      "owner": "Only if explicit in the update",
      "due_date": "Only if explicit in the update",
      "severity": "Only if explicit in the update",
      "source_label": "Source title or label if supplied",
      "source_url": "Source URL if supplied"
    }
  ],
  "source_note": "Optional short note about selected scope"
}
```

Keep card text concise but complete enough for a presenter to act. Use plain
business language. Do not include markdown tables.
