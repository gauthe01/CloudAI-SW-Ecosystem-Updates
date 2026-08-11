# Feature 26 - Global Loading Experience

## Purpose

Feature 26 replaces plain text loading states with a reusable branded loader for
screen-level and module-level waits across the Cloud AI Software Ecosystem
Updates app.

## Scope

- Add a shared frontend loader component that can be used from any screen.
- Use an animated visual that feels specific to ecosystem signal processing,
  not a generic spinner.
- Keep loading copy clear and contextual.
- Respect reduced-motion preferences.
- Apply the loader to presenter AI-generation waits and key workspace loading
  transitions.

## Initial Implementation

- `GlobalLoader` lives in `apps/web/src/components/foundation/GlobalLoader.tsx`.
- Styles live in the global stylesheet so the component can be used anywhere in
  the app without feature-specific CSS.
- Presenter screens use it for:
  - Executive Summary generation.
  - Decision Board generation.
  - Partner Intelligence loading.
  - Event Calendar loading.
  - Draft Email generation.
- Contributor and shell screens use it for:
  - Initial workspace loading.
  - Assigned partner loading.
  - Contributor dashboard loading.
  - Partner metadata loading.

## Acceptance Criteria

- Loading states no longer appear as plain text on the primary presenter and
  workspace screens.
- The loader is centered within the available panel or page area.
- The loader includes a clear label and optional supporting detail.
- Animation is disabled when the user prefers reduced motion.
- The component can be reused by importing `GlobalLoader`.
