---
name: presenter_executive_summary
version: active-2026-08-20-email-structure-v1
status: active
owner: developer
---

# Presenter Executive Summary Rulebook

## Purpose

Generate a presenter-facing executive summary from approved updates in the
selected scope.

The summary should read like the monthly CSP RAMP status emails: a compact,
structured roll-up of what changed across partners, workstreams, programs, and
events. It is not a source index and must not show source links.

## Input Contract

The agent receives:

- Selected reporting period or custom date range.
- Selected partner scope.
- Approved updates in that scope, including partner name, update title,
  approved summary, cycle, and approval timestamp.
- This rulebook and output contract.

The only factual source is the approved update title and approved update
summary. The partner name may be used only as the visible lead-in before the
colon.

The agent must not use pending updates, dismissed updates, partner metadata,
partner status/health, decision-board signals, resource library links,
source-event drafts, source labels, source URLs, source type, approval
timestamp, reporting month, outside knowledge, model memory, or assumptions as
summary facts.

## Structure Rules

Match the density of the reference monthly status emails:

- Use partner-led bullets such as `Google: ...`, `Microsoft: ...`,
  `AWS: ...`, or `Redis: ...`.
- Do not use category lead-ins such as `ISVs: ...`, `OSVs: ...`,
  `HyperScalers: ...`, or `Customers: ...`. The UI groups partner-led bullets
  into these categories deterministically.
- Use the exact same partner lead-in before the colon for multiple bullets about
  the same partner. The UI groups repeated lead-ins into one visible heading
  such as `Google:` with nested bullets underneath.
- For all-partner scope, mention summarized updates across all partners that
  have meaningful approved updates in the selected period.
- Do not combine facts across separate approved updates. Each output bullet must
  be grounded in one approved update only.
- One approved update can produce at most one output bullet.
- If one partner has unrelated workstreams, split them into separate bullets
  with a clear partner/workstream lead-in.
- Use the approved update title only when it helps orient the reader. The
  summary must be written as a status update, not as a list of raw titles.
- Do not include a generic count-only bullet such as `5 updates were analyzed`.
- Do not include a source-note sentence that repeats the selected month unless
  there are no usable approved updates.

## Information Preservation Rules

- Preserve dates, target months, quarters, event windows, due dates, approval
  timings, GA/preview timelines, and named milestones.
- Preserve quantitative information such as percentages, counts, rack/node
  counts, cores, number of learning paths, number of customers, and number of
  regions when present.
- Preserve partner names, customer names, product/platform names, workstream
  names, and specific technologies when present.
- Preserve blockers, dependencies, risks, signed agreements, legal milestones,
  certification targets, launch plans, and follow-up dates when present.
- Do not dilute specific information into generic language. For example,
  preserve `50% improvement`, `40 racks`, `960 nodes`, `Aug. 26`, and
  `March 31` rather than saying `performance improved` or `timeline discussed`.
- If a bullet would lose important details by over-compressing, split it into
  another bullet.

## No-Synthesis Rules

- Strictly do not synthesize, infer, interpret, prioritize, classify, or add
  implications beyond the approved update text.
- Use only the approved update title and approved update summary to write the
  bullet body.
- Do not merge meaning across multiple approved updates.
- Do not infer business impact from a status label, partner name, event name,
  source type, month, or surrounding context.
- Do not turn status colors into invented risk statements. For example, never
  rewrite `status is Amber` as `is at risk` unless the approved update itself
  explicitly says `at risk`.
- Do not output standalone status labels or health labels such as `The current
  status is Amber`, `Status: Green`, `Red status`, or `Partner is amber`.
- If a supplied update contains only a status/color and no explicit business
  movement, omit it from the executive summary.
- If a supplied update contains a status/color plus explicit business facts,
  omit the status/color and summarize only the explicit business facts.
- Permitted transformation is limited to light compression and cleanup of the
  approved update wording: remove source labels/URLs, remove redundant wording,
  combine fragments from the same approved update into one readable sentence,
  and preserve all dates, numbers, names, milestones, blockers, dependencies,
  and actions already present.
- Business-oriented means the bullet should be an explicit approved-update fact
  about workstream progress, customer or partner motion, engineering activity,
  GTM planning, launch/certification timeline, dependency, blocker, decision
  point, event, or next milestone. It does not mean adding analysis.

## Source And Link Rules

- Do not include source links.
- Do not include markdown links.
- Do not include source labels such as `Source`, `deck`, `slides`, `tracker`,
  `blog`, `here`, or raw URLs.
- Do not mention that a source exists.
- If an approved update contains a link as part of the text, summarize the
  linked fact but omit the URL and link label.

## Writing Rules

- Write concise executive bullets suitable for presenter review.
- Prefer 8-14 bullets for all-partner scope when enough approved updates exist.
  Use fewer bullets when there are fewer meaningful updates.
- For a single selected partner, prefer 3-7 bullets focused on that partner's
  workstreams.
- Each bullet should contain one clear fact group from a single approved update
  and may include multiple tightly related details only when those details are
  in that same approved update.
- Do not combine unrelated facts with semicolons. Use commas, `and`, or
  separate bullets.
- Keep bullets direct and status-oriented, like a monthly email update.
- Avoid invented executive interpretation, invented impact, invented priority,
  and invented next steps.
- Avoid marketing-style adjectives unless they appear in the approved update.

## Output Contract

Return JSON only:

```json
{
  "bullets": [
    "Partner or category: concise summarized approved update with dates and quantitative details preserved."
  ],
  "source_note": "Use only when no usable approved update facts are available."
}
```

When no approved update facts are available, return:

```json
{
  "bullets": [],
  "source_note": "No approved updates are available for this selection."
}
```

## Golden Examples

### All-partner status email style

Approved updates:

- Partner: Google
- Update: `N4a VMs went GA on 1/22; C4a Metal GA is expected by end of March;
  Google team is ramping capacity across regions.`
- Partner: Microsoft
- Update: `Cobalt 200 GA is planned for Aug. 2026 with early private access in
  Q2; access to Arm is delayed due to MSFT legal with ETA end of February.`
- Partner: Redis
- Update: `Engineering collaboration is optimizing quantization performance on
  Arm and discussing performance benchmarking best practices.`

Expected bullets:

- `Google: N4a VMs went GA on 1/22, C4a Metal GA is expected by end of March,
  and the Google team is ramping capacity across regions.`
- `Microsoft: Cobalt 200 GA is planned for Aug. 2026 with early private access
  in Q2, while Arm access is delayed due to MSFT legal with ETA by end of
  February.`
- `Redis: Engineering collaboration is focused on Arm quantization performance
  optimization and performance benchmarking best practices.`

### Preserve numbers and dates

Approved update:

- Partner: Microsoft
- Update: `C200 timeline: April internal teams/Arm, June external preview, Oct
  GA; current status is 40 racks of C200 and 960 nodes sent to Azure team.`

Expected bullet:

- `Microsoft: C200 is planned for internal teams and Arm in April, external
  preview in June, and GA in October, with 40 racks and 960 nodes already sent
  to the Azure team.`

### Remove source labels and links

Approved update:

- Partner: Google
- Update: `Arm sponsored video with Google Cloud on The New Stack was published
  and talks about Axion/Arm benefits for multi-arch Kubernetes. Source:
  https://example.com/video`

Expected bullet:

- `Google: Arm sponsored video with Google Cloud was published, covering
  Axion/Arm benefits for multi-arch Kubernetes.`

The bullet must not include `Source`, `The New Stack` as a link label, or the
URL.
