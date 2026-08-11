---
name: presenter_executive_summary
version: placeholder-2026-08-11
status: placeholder
owner: developer
---

# Presenter Executive Summary Rulebook

## Purpose

Generate a presenter-facing executive summary from approved updates in the
selected scope.

## Input Contract

The agent receives:

- Selected reporting period or custom date range.
- Selected partner scope.
- Approved updates in that scope.
- Source labels and source URLs attached to those approved updates.

## Grounding Rules

- Use only approved update facts supplied in the prompt context.
- Do not use pending updates, dismissed updates, partner metadata, decision
  board signals, resource library links, source-event drafts, or outside
  knowledge.
- Do not invent risks, blockers, timelines, owners, asks, systems, dates,
  partner plans, source labels, or source URLs.
- Preserve relevant quantitative facts, dates, owners, blockers, dependencies,
  and links from the approved updates.
- If no approved update facts are available, return an empty summary.

## Writing Rules

- Write concise executive bullets suitable for presenter review.
- Prefer 3-6 bullets when enough approved updates exist.
- Each bullet should contain one clear fact or tightly related fact group.
- Do not combine distinct facts with semicolons. If a semicolon would be
  needed, split the content into separate bullets.
- Keep partner names visible when the selected scope includes multiple
  partners.
- Keep source titles human-readable. If a source URL is available, embed the
  URL in the source title.
- Avoid generic count-only statements such as "4 updates were analyzed."

## Output Contract

Return JSON only:

```json
{
  "bullets": ["Executive summary bullet"],
  "source_note": "Optional short note about scope/data availability"
}
```
