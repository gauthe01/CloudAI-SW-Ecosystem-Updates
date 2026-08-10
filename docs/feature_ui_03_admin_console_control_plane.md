# UI Feature 03 - Admin Console Control Plane

Product: Cloud AI Software Ecosystem Updates
Status: implemented locally

## Purpose

Create an Admin Console landing state that behaves like a control plane instead
of dropping the admin directly into one module.

## Reference

The card grid follows the legacy Admin Console home reference supplied during UI
review, but it intentionally keeps the new shared dark navbar from UI Feature 02.

## Scope

- Added an `Admin Console` landing section.
- Added reusable admin module cards for:
  - Partners
  - Team Members
  - Global Integrations
  - Connected Sources
  - Knowledge Upload
- Each card opens the existing module panel.
- Module views include a `Back to Admin Console` action.
- Admin module tabs are hidden inside card-selected module views to keep the
  card grid as the only Admin module selector.
- Admin module pages use a shell-owned action row for back navigation and
  screen-level CTAs.
- Backlog/disabled cards are not shown.

## Implementation Notes

- `AdminControlPlanePanel` owns the card grid and lightweight summary counts.
- The existing Team, Partners, Knowledge Upload, Global Integrations, and Source
  Approvals panels were not rewritten.
- Summary calls use `Promise.allSettled` so one failed count does not block the
  console cards.

## Acceptance Checks

- Admin lands on the card-grid control plane.
- Clicking a card opens the correct existing module.
- Admin module views do not show the module-tab selector.
- The page header can return to the card-grid console.
- The navbar remains the finalized shared navbar.

## Iteration 2

- Updated card order to:
  Partners, Team Members, Global Integrations, Connected Sources, Knowledge
  Upload.
- Replaced the ASCII card arrow with the right-arrow glyph used in the visual
  reference.
- Kept `Connected Sources` wired to the existing Source Approvals module until
  that screen is renamed/refined in its own UI feature.
