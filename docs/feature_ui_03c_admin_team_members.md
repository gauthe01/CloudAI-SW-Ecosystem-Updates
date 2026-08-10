# UI Feature 03C - Admin Team Members

Product: Cloud AI Software Ecosystem Updates
Status: implemented locally

## Purpose

Bring the Admin Console Team Members module into the same visual and structural
pattern as the completed Admin Partners module.

## Scope

- The admin module title uses the Admin Console card display label:
  `Admin Console - Team Members`.
- The internal route id remains `Team` so existing API and navigation logic stay
  stable.
- Removed the duplicate inner `Admin Console` / `Team` module heading.
- Moved the create-member CTA into the shared shell action row.
- Styled the create-member CTA like the Partners `Add Partner +` action.
- Capitalized Team and access-request status labels.
- Kept Team status pills on the same shared `status-pill` visual system as
  Partners.
- Added the Team table `Action` column heading.
- Sorted active members first A-Z by display name, then deactivated members A-Z.

## Acceptance Checks

- Clicking the `Team Members` Admin Console card opens the Team Members module.
- The page title reads `Admin Console - Team Members`.
- The page does not render a second inner `Admin Console` / `Team` heading.
- `Add Member +` appears in the same header action location and visual style as
  `Add Partner +`.
- Team table statuses read `Active` and `Deactivated`, not lowercase values.
- Deactivated members appear below active members.
