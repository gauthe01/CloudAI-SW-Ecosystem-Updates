---
name: admin_knowledge_upload
version: feature-24-2026-08-13
status: active
owner: developer
---

# Admin Knowledge Upload Rulebook

## Purpose

Extract grounded, reviewable partner updates from admin-uploaded knowledge files
so an admin can confirm them before they become pending contributor updates.

## Input Contract

The extractor receives one uploaded document, extracted text blocks, source file
metadata, optional selected partner context, known active partners, and any
detected cycle/month hints.

## Extraction Rules

- Use only facts present in the uploaded source blocks. Do not add AI synthesis,
  background knowledge, assumptions, or invented bridge text.
- Extract every meaningful partner update, not just the first one.
- Keep each candidate distinct and self-contained.
- Read monthly status reports as an outline, not as flat bullets. A top-level
  partner or category bullet establishes context. The next inward bullet level
  creates separate update candidates. Deeper bullets remain nested inside that
  candidate exactly as source structure.
- A partner container with no child update bullets creates no candidate. For
  example, `AWS:` with no inward child bullets produces zero AWS updates.
- Under a partner such as `Google:`, every immediate child bullet is one update.
  If that child has nested bullets, keep those nested bullets inside the same
  update rather than creating separate candidates for them.
- Under a partner such as `Microsoft:`, child bullets aligned at the same inward
  level are separate updates. Wrapped unbulleted continuation lines belong to
  the previous update.
- Preserve list hierarchy visually in the candidate summary with nested lists.
- Preserve all quantitative facts, dates, named systems, owners, priorities,
  severities, dependencies, document references, and links that appear in the
  source item.
- If a source item contains links, include the link in the same candidate where
  the linked source item is used.
- Preserve embedded hyperlinks as source link metadata attached to the candidate
  whose text contained the link. Do not replace linked text with invented URL
  wording.
- Do not merge separate updates. If a semicolon would be needed, create separate
  bullets or separate candidates instead.
- Carry partner context from headings and parent bullets. If a bullet appears
  under `Google`, then nested children such as `10x10 booth with demos` belong
  to Google unless another explicit partner context overrides it.
- Treat partner-type headings such as `ISVs` and `OSVs` as category context, not
  partner names.
- Under a category such as `ISVs (...)`, child bullets with leading labels such
  as `Redis:`, `VMware:`, `Elastic:`, `Salesforce:`, `MongoDB:`, `Tinkerblox:`,
  `Cohere:`, or `Uber` establish the partner for that update or subsection.
- If a partner-type heading includes bracketed partner names, such as
  `OSVs (Red Hat, SUSE, Canonical)`, fan out each meaningful child update to all
  listed partners while preserving the same source evidence for each candidate.
- If child bullets under a category begin with a partner label, such as
  `Redis: ...` or `VMware: ...`, map the update to that leading partner label
  and keep the update text after the partner prefix.
- If a category lists partners in parentheses, every child update subtree under
  that category is cloned to every listed partner. For `OSVs (Red Hat, SUSE,
  Canonical)`, the same nested update appears once for Red Hat, once for SUSE,
  and once for Canonical.
- Assign the candidate to the source item month when the source item has a
  timestamp or month. If only the document has a cycle, use the document cycle.
- Do not repeat prior-month information when a later source item only introduces
  one new fact. Extract only the net-new fact from that source item.
- Meeting notes may yield separate candidates for decisions, concrete next
  actions, blockers, partner commitments, and timeline changes.
- Trackers and spreadsheets may yield separate candidates per meaningful row.
- Decks may yield separate candidates per key milestone, status, dependency,
  goal, or partner-facing commitment.
- Google workstream PowerPoint decks are row-based, not flat slide text. In
  tables with `Workstream`, `CY2026 Targets`, and `Recent Updates` columns, each
  non-header row is one Google update. Render the workstream name, all target
  bullets, and all recent-update bullets inside that one candidate. Preserve
  nested bullets and embedded links.
- Microsoft workstream PowerPoint decks are workload-row based. In dashboard
  tables with `Workstream`, `Workload`, `Objective`, `Updates...`,
  `Go to Green Action`, and `RAG` columns, create one Microsoft update per
  workload row. Inherit blank workstream cells from the previous row. If a row
  contains multiple workload lines with matching objective lines, split them
  into separate updates. Preserve update bullets, include go-to-green action
  when present, and translate the color-only RAG cell into `Current Status`.

## Ignore Rules

- Ignore pure logistics, greetings, duplicate headers, footers, version history,
  and formatting-only rows or slides.
- Ignore document metadata such as cover titles, report titles, and
  `Monthly Status Report - <month> <year>` lines.
- Ignore vague intentions with no outcome, owner, milestone, blocker, dependency,
  or committed next action.
- Keep top-level non-partner topic headings visible in Resolve instead of
  dropping them. Examples include Ecosystem Projects, Marketing, Upcoming
  Conferences and Events, and Upcoming PTO.
- If a topic/workstream heading appears inside an active partner section, keep it
  under that partner and preserve its child bullets. Do not drop partner-scoped
  workstreams merely because the same label could be a general topic elsewhere.
- Keep non-partner topic content out of partner commit until the product supports
  configured topic/workstream knowledge records.
- Ignore content that cannot be mapped to a partner or configured topic unless
  the admin can clearly resolve it during review.

## Output Contract

Return structured candidates with summary, partner mapping if known, cycle month
if known, source evidence, source location, links, confidence, and review status.
Candidates that lack partner or cycle mapping must remain reviewable but blocked
from staging until the admin resolves the missing mapping.
