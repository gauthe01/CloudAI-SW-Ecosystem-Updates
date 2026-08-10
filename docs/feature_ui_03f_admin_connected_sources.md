# UI Feature 03F - Admin Connected Sources

Product: Cloud AI Software Ecosystem Updates
Status: implemented locally

## Purpose

Refine the Admin Connected Sources module so it uses the same shell-owned
heading pattern as the other Admin Console modules and only shows review detail
when an admin explicitly selects a request.

## Scope

- Removed the duplicate inner `Admin Console` / `Source Approvals` heading.
- Kept the shell title as `Admin Console - Connected Sources`.
- Removed the initial auto-selection of the first connected source.
- Queue tab changes clear the current selection.
- The review detail panel is hidden until a source row is clicked.
- The source table uses full width when no review detail panel is open.
- After a source row is selected, the table and review panel use the existing
  split layout.

## Queue Semantics

- `Needs Review` means a contributor has submitted a source request and it is
  pending admin review.
- `Attention` means the source is not in the normal approval path and needs
  follow-up, such as access setup, disabled state, or failed readiness.
- `Active` means approved and enabled for update generation.
- `Rejected` means admin rejected the request.
- `All` shows every source regardless of bucket.

## Acceptance Checks

- Connected Sources renders without an inner duplicate module heading.
- Review detail is hidden on initial load.
- Review detail stays hidden when switching queues.
- Clicking a source row opens the review detail panel.
