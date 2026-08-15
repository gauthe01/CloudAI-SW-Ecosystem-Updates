---
name: admin_knowledge_upload.microsoft_workstreams_ppt
version: feature-24-microsoft-workstreams-2026-08-15
status: active
owner: developer
---

# Microsoft Workstreams PPT Rulebook

## Purpose

Extract reviewable Microsoft partner updates from Microsoft workstream dashboard
decks.

## Input Contract

The extractor receives a Microsoft workstream PowerPoint deck, slide/table text,
source file metadata, known active partners, and detected reporting-period hints.

## Extraction Rules

- Treat the whole deck as Microsoft partner knowledge unless a later rulebook
  says otherwise.
- Ignore cover, leads, RAG-definition, appendix, and blank slides.
- Find dashboard tables with `Workstream`, `Workload`, `Objective`,
  `Updates...`, `Go to Green Action`, and `RAG` columns.
- Each dashboard workload row is one candidate update.
- If the workstream cell is visually merged or blank, inherit the nearest
  previous non-empty workstream label.
- If one row contains multiple workload lines and matching objective lines,
  split it into one candidate per workload/objective pair.
- Render each candidate in this order:
  - `<workstream> Work Stream`
  - `Workload: ...`
  - `Objective: ...`
  - `Updates & Blockers:` with the source bullets preserved
  - `Go to Green Action: ...` when present
  - `Current Status: ...`
- Convert the color-only RAG cell into a text status: Green, Amber, Red, or
  Gray. Yellow and orange RAG fills both mean Amber.
- Preserve embedded hyperlinks on the linked text and attach the link to source
  evidence.
- Use the reporting month from the filename when available. Row-level dates are
  source details, not the reporting period.
- Do not invent missing actions, statuses, owners, dates, or objectives.

## Output Contract

Create Microsoft candidates that are document-shaped rich HTML and are ready for
admin approval when Microsoft and the reporting period are known.
