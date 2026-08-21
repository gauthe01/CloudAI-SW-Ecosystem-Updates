---
name: executive_email
version: active-2026-08-20-email-generator-v1
status: active
owner: developer
---

# Executive Email Rulebook

## Purpose

Generate an editable presenter email draft from approved updates in the selected
period and partner scope.

The email should follow the same monthly status-update pattern as the CSP RAMP
reference emails and the presenter executive summary: concise, grouped,
business-readable, and grounded only in approved update content.

## Input Contract

The email generator receives:

- Selected reporting period or custom date range.
- Selected partner scope.
- Approved updates in that scope, including partner name, title, summary, cycle,
  and approval metadata.

Approved update title and approved update summary are the only factual source.
Do not use pending updates, dismissed updates, partner metadata, decision-board
signals, source URLs, source labels, model memory, outside knowledge, or
assumptions as email facts.

The generated output is an editable draft. Users may adjust the subject or body
before copying.

## Writing Rules

- Use the email frame:
  - `Hello,`
  - `Please find the approved <period> update for <scope>:`
  - grouped update sections
  - `Regards,`
- For all-partner or multi-partner scope, group partner updates by:
  - `HyperScalers`
  - `OSVs`
  - `ISVs`
  - `Customers`
  - `Other Partners`
- Under each category, show each partner once as `Partner name:` and list that
  partner's update lines as bullets.
- Format category headings and partner headings as bold when rendered in the
  editable email preview.
- Format each update line as a tab-indented hyphen bullet:
  `\t- H2 2026 GTM plan being developed, with a focus on Cobalt 200 Oct GA & Ignite presence. Discussion at APM to review.`
- For a single selected partner, omit category headings and show the partner
  name once followed by bullets.
- Do not use a numbered raw dump of every update.
- Keep each bullet grounded in one approved update. Do not merge unrelated facts
  across updates.
- Preserve dates, percentages, counts, milestones, target months, blockers,
  dependencies, launch/certification plans, and named programs when present.
- Do not invent analysis, implications, priorities, or next steps.
- Do not include raw URLs, markdown links, source labels, or `Source:` text.
- If a link label is part of an approved update, keep the business fact but omit
  the URL.
- If no approved updates exist, state that no approved updates are available for
  the selected scope and period.

## Ignore Rules

- Ignore source labels, source URLs, source types, approval timestamps, and
  source-only link text.
- Ignore status/color-only statements when they contain no business update.
- Ignore any fact not present in the approved update title or summary.

## Output Contract

The email generator returns:

```json
{
  "subject": "Partner Ecosystem Monthly Update - July 2026",
  "body": "Hello,\n\nPlease find the approved July 2026 update for the Cloud AI Software Ecosystem:\n\nISVs:\nVMware:\n\t- ...\n\nRegards,"
}
```

The frontend must allow the user to edit both fields before copying.
