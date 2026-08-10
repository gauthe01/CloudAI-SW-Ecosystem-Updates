# UI Feature 03E - Admin Global Integrations

Product: Cloud AI Software Ecosystem Updates
Status: implemented locally

## Purpose

Restructure the Admin Global Integrations module so admins configure one global
integration at a time from a tabbed selector, while preserving the existing
integration credential card design.

## Scope

- Removed the duplicate inner `Admin Console` / `Global Integrations` heading.
- Removed the `Admin scope` information banner from the module body.
- Added integration switch tabs directly below the shared workspace heading.
- Tab ordering places configured integrations first, sorted A-Z by display
  name.
- Non-configured integrations appear after configured integrations, also sorted
  A-Z by display name.
- Only the selected integration card is shown.
- The existing boxed integration credential editor is retained for this
  iteration.

## Acceptance Checks

- The page title reads `Admin Console - Global Integrations`.
- No duplicate inner module heading is rendered.
- No `Admin scope` banner is rendered.
- Global integration tabs are visible below the workspace heading.
- Configured tabs appear before non-configured tabs.
- Selecting a tab swaps the visible integration card.
