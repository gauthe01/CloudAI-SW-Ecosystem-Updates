# UI Feature 05 - Contributor Partner Selection And Dashboard Shell

## Status

Implemented.

## Scope

- Keep the existing application navbar unchanged.
- Rebuild the contributor-only content below the navbar using the Gold project as visual reference.
- Support multi-partner contributor selection before entering a partner workspace.
- Preserve one-partner contributor flow by landing directly in the contributor dashboard.
- Use the approved underline tab style for contributor sections.

## Implemented Screens

### Partner Selection

- Gold-style greeting header.
- Assigned partner count.
- Search input for assigned partners.
- Partner workspace cards with:
  - Colored top border.
  - Initials tile.
  - Partner name.
  - Description fallback.
  - Updates count.
  - Integrations count.
  - Last active footer.

### Contributor Dashboard Shell

- Partner header with last activity.
- Search updates input.
- Reporting cycle selector.
- Existing `+ Add update` entry button retained.
- Section tabs:
  - Pending
  - Approved
  - Partner metadata
  - Connected sources
- Pending and Approved tabs show count badges.

## Deferred

- Add Update screen redesign is intentionally paused for later discussion.
- No navbar redesign was included in this feature.

## Verification

- `pnpm typecheck:web`
- `pnpm build:web`
- `docker compose build --pull=false web`
- `docker compose up -d --no-deps web`
- Browser smoke:
  - Bhumik Patel one-partner contributor flow.
  - Sameer Nori multi-partner contributor selection flow.
