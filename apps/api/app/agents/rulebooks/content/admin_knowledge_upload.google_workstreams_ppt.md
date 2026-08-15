---
name: admin_knowledge_upload.google_workstreams_ppt
version: feature-24-google-workstreams-2026-08-15
status: active
owner: developer
---

# Google Workstreams PPT Rulebook

## Purpose

Extract reviewable Google partner updates from Google workstream status decks.

## Input Contract

The extractor receives a Google workstream PowerPoint deck, slide/table text,
source file metadata, known active partners, and detected reporting-period hints.

## Extraction Rules

- Treat the whole deck as Google partner knowledge unless a later rulebook says
  otherwise.
- Ignore cover, intro, process, agenda, appendix, and non-table slides.
- Find slides with the `Workstream`, `CY2026 Targets`, and `Recent Updates`
  table columns.
- Each non-header table row is exactly one candidate update.
- The first column gives the workstream name. Render it as
  `<workstream> work stream`.
- The second column becomes `CY2026 Targets:` and keeps its bullets in the
  source order.
- The third column becomes `Recent Updates:` and keeps its bullets in the
  source order.
- Preserve nested bullets inside the same row. Do not split child bullets into
  separate candidates.
- Preserve embedded hyperlinks on the linked text and attach the link to source
  evidence.
- Use the reporting month from the filename when available.
- Do not invent missing targets, update text, owners, dates, or next meetings.

## Output Contract

Create one Google candidate per workstream row. The candidate summary must be
document-shaped rich HTML that contains the workstream title, `CY2026 Targets`,
and `Recent Updates` sections.
