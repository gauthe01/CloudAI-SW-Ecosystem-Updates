# UI Feature 02 - Workspace Shell Navigation

Product: Cloud AI Software Ecosystem Updates
Status: implemented locally

## Purpose

Stabilize the shared app frame before deeper screen-by-screen UI polish.

The goal is to avoid repeating navbar, account menu, tab, and product-name
markup across screens. Shared shell elements should be reusable and consistent
for Contributor, Presenter, and Admin views.

## Components Added

- `AppTopNav`
  - Reusable top navigation/header wrapper.
  - Displays product eyebrow, current workspace title, and right-side actions.

- `AccountMenu`
  - Reusable account dropdown.
  - Displays user identity, available views, active view, and sign out.
  - Handles outside-click close internally.

- `SectionTabs`
  - Reusable tab strip for workspace sections.
  - Used by Admin and Presenter view sections.

- `productName`
  - Single source of truth for the product name.
  - Used by login, request access, layout metadata, and workspace shell.

## Behavioral Scope

- No business logic changed.
- Existing Contributor, Presenter, and Admin routing remains the same.
- Existing role-based account switching remains the same.
- Login and request-access pages keep their current layout, but now use the
  shared product name constant.

## Implementation Notes

- Shell labels and section order now live in `features/shell/navigation.ts`.
- `AccountViewShell` now coordinates state and content rendering instead of
  owning navbar and account-menu internals.
- `AccountMenu` is typed generically so callers keep their own view id type.

## Deferred

- Visual redesign of the navbar.
- Applying `SectionTabs` to contributor dashboard tabs.
- Extracting table, panel, and form primitives from admin/contributor screens.
