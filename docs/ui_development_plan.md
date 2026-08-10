# UI Development Plan

Product: Cloud AI Software Ecosystem Updates
Status: planning document, not implementation

## 1. Purpose

This document converts the UI workshop notes, PRD, backend feature plan, current
UI audit, and implemented feature docs into a sequenced client-side development
plan.

The goal is to avoid rebuilding the UI as one large pass. The UI should be
implemented as small, testable features that map to the product's real user
flows:

- Contributor maintains partner context and reviews updates.
- Presenter reads approved intelligence across all partners.
- Admin configures the system and reviews source requests.

This document does not authorize implementation by itself. The decision gates in
section 4 must be answered before any UI code changes begin.

## 2. Source Documents

This plan is based on:

- `product_requirements_document.md`
- `sequential_feature_build_plan.md`
- `ui_reuse_gap_assessment.md`
- `current_project_reuse_assessment.md`
- `pending_tasks_and_blockers.md`
- `feature_02_auth_sessions_local_login.md`
- `feature_04_admin_team_users.md`
- `feature_07_contributor_dashboard_shell.md`
- `feature_08_partner_metadata_resource_library.md`
- `feature_09_update_lifecycle.md`
- `feature_10_manual_add_update.md`
- `feature_11_file_knowledge_upload.md`
- `feature_12_contributor_connected_sources.md`
- `feature_13_admin_global_integrations.md`
- `feature_14_admin_connected_source_approvals.md`
- `feature_21_presenter_intelligence_draft_email.md`

## 3. Current UI State

The current rebuilt client is functional but not yet visually matched to the
legacy approved UI. The backend feature sequence is mostly implemented locally,
and the client contains working screens for:

- Login
- Role-aware shell and account view switching
- Admin Team
- Admin Partners
- Admin Knowledge Upload
- Admin Global Integrations
- Admin Connected Source Approvals
- Contributor Partner Selection
- Contributor Dashboard Shell
- Contributor Partner Metadata
- Contributor Pending and Approved Updates
- Contributor Manual Update
- Contributor Connected Sources
- Contributor Partner Files
- Presenter Workspace

The current React files that will likely be touched during the UI pass are:

- `apps/web/src/app/globals.css`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/login/page.tsx`
- `apps/web/src/features/auth/LoginForm.tsx`
- `apps/web/src/features/shell/AccountViewShell.tsx`
- `apps/web/src/features/admin/AdminTeamPanel.tsx`
- `apps/web/src/features/admin/AdminPartnersPanel.tsx`
- `apps/web/src/features/admin/AdminKnowledgeUploadPanel.tsx`
- `apps/web/src/features/admin/AdminIntegrationsPanel.tsx`
- `apps/web/src/features/admin/AdminSourceApprovalsPanel.tsx`
- `apps/web/src/features/contributor/ContributorPartnerSelectionPanel.tsx`
- `apps/web/src/features/contributor/ContributorDashboardShell.tsx`
- `apps/web/src/features/contributor/ContributorPartnerMetadataPanel.tsx`
- `apps/web/src/features/contributor/ContributorUpdatesPanel.tsx`
- `apps/web/src/features/contributor/ManualUpdateForm.tsx`
- `apps/web/src/features/contributor/ContributorConnectedSourcesPanel.tsx`
- `apps/web/src/features/contributor/ContributorUploadsPanel.tsx`
- `apps/web/src/features/presenter/PresenterWorkspacePanel.tsx`

## 4. Decision Gates Before Implementation

These items conflict across notes or are not yet final. They should be answered
before UI work begins.

### Gate 1 - Landing Page

Conflicting notes:

- UI workshop: keep landing page plus login page for now.
- UI audit: marketing-style landing page is not product-appropriate and should
  not be used in the rebuilt app.

Decision:

- Do not keep a separate landing page.
- `/` should lead to the authenticated app when a session exists, otherwise to
  the sign-in page.
- The sign-in page is the unauthenticated product entry point.

### Gate 2 - Admin Password Controls

Conflicting notes:

- PRD and UI audit mention Admin-managed pilot passwords.
- Feature 04 implemented Team UI with no password set/reset fields.
- Feature 04 says local pilot credentials are controlled through environment
  configuration.

Decision:

- Keep no password reset UI for now.
- Admin-created local pilot users use the configured local default password.
- Self-requested users choose their password in the request form.
- Admin approval requires at least one selected role and creates the user with
  those roles.
- Presenter pilot access still requires a password until ARM SSO is configured.

### Gate 3 - Word Report UI

Conflicting notes:

- PRD includes Word monthly report generation and download in v1.
- Feature 21 and pending blockers say no Word report UI for now unless promoted.

Decision needed:

- Include Word report UI in this UI pass, or
- Keep Word report out of this UI pass and leave it in backlog.

### Gate 4 - Presenter Ask AI

Conflicting notes:

- Older UI notes list Ask AI as reusable.
- Feature 21 says Ask AI orchestration is not in scope unless promoted.

Decision needed:

- Hide Ask AI completely for this pass, or
- Keep an inactive/placeholder side panel, or
- Promote Ask AI to a real planned feature later.

### Gate 5 - Metadata Sections

Conflicting notes:

- PRD required metadata fields are Highlights / Status, Business Priority,
  Goals, Key Risks & Issues, and Resource Links.
- Sequential feature plan and implemented Feature 08 kept additional current
  sections: Why This Partner and Execution Timeline.

Decision needed:

- Keep all current metadata sections for UI parity, or
- Remove Why This Partner and Execution Timeline to match the stricter PRD.

### Gate 6 - Knowledge Upload / Partner Files Visibility

Conflicting notes:

- Feature 11 implemented Admin Knowledge Upload and Contributor Partner Files.
- UI audit says Knowledge Upload may be optional/backlog if not immediate v1
  scope.

Decision needed:

- Keep both Admin Knowledge Upload and Contributor Partner Files visible, or
- Hide one or both until later.

### Gate 7 - Contributor Connected Source Status Labels

Conflicting notes:

- PRD says Contributor should mainly see Pending, Active, and Rejected.
- Feature 12 UI supports more statuses such as disabled, archived, failed, and
  paused/resumed states.

Decision needed:

- Show simple contributor labels only, or
- Show broader operational statuses to contributors.

### Gate 8 - Pending Figma Designs

Design-pending items from the feature plan:

- Contributor Connected Sources
- Admin Global Integrations
- Admin Connected Source Approvals

Decision needed:

- Wait for user-provided Figma screens before restyling these, or
- Use the current functional UI as the design basis and polish it.

### Gate 9 - Mobile Priority

The UI audit says mobile is functional but not polished.

Decision:

- Desktop/tablet first.
- Mobile should remain usable and non-broken, but this pass should not create a
  dedicated mobile version or mobile-first navigation model.

## 5. UI Build Principles

These principles are already supported by the docs and should apply to every UI
feature.

- Reuse approved visual patterns from the old project where the user explicitly
  said "keep as-is".
- Do not reintroduce workstreams, polling, PowerPoint export, signup,
  self-service forgot password, rulebook editing, or raw source excerpt UI.
- Keep Contributor View assignment-scoped.
- Keep Presenter View globally read-only.
- Keep Admin View as the control plane.
- Keep Resource Links separate from Connected Sources.
- Keep global integration credentials separate from contributor source config.
- Use approved updates as the official truth.
- Make loading, empty, error, and permission states visible and calm.
- Keep the interface compact and operational, not marketing-heavy.

## 6. Recommended Feature Sequence

### UI Feature 00 - UI Source Of Truth And Visual Baseline

Goal:

Create a stable visual foundation before restyling individual screens.

Screens affected:

- All screens.

Scope:

- Define global page width, spacing scale, typography scale, color tokens, table
  styles, form styles, status pills, buttons, tabs, cards, modals, drawers, and
  empty states.
- Align the current React app with the legacy visual direction:
  - dark navy shell accents
  - teal primary actions
  - light gray workspace background
  - compact dense tables
  - low-radius cards and panels
- Establish shared status colors:
  - Green / Amber / Red for metadata health
  - Pending / Active / Rejected / Disabled / Failed for operational states
- Define responsive rules for desktop/tablet/mobile before page work begins.

Implementation targets:

- `apps/web/src/app/globals.css`
- Optional shared UI helper components if duplication becomes high.

Acceptance criteria:

- No product workflow changes.
- Existing screens still load.
- Buttons, tabs, tables, inputs, cards, and status pills use consistent styling.
- Text does not overflow buttons, table cells, status pills, or compact panels.

Dependencies:

- Decision Gate 9 for mobile priority.

### UI Feature 01 - Auth Entry And Login

Goal:

Finalize unauthenticated entry and local login UI for the pilot.

Screens affected:

- Landing page
- Login page

Confirmed requirements:

- App name is Cloud AI Software Ecosystem Updates.
- Login uses email and password.
- Keep show/hide password.
- Keep keep-signed-in checkbox.
- No self-signup.
- No OTP.
- No visible password values.
- Remove Forgot Password and Create Account links.

Open decisions:

- Gate 1: landing page behavior.
- Gate 2: Admin password control model affects login help/error copy.

Scope:

- Match the approved split login screen visual.
- Remove legacy links.
- Improve failed-login message only after password-control decision is final.
- Ensure labels are accessible and do not conflict.

Implementation targets:

- `apps/web/src/app/page.tsx`
- `apps/web/src/app/login/page.tsx`
- `apps/web/src/features/auth/LoginForm.tsx`
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Unauthenticated user reaches the agreed entry screen.
- Login form matches approved visual direction.
- Forgot password and Create Account are not visible.
- Failed login state is readable and not misleading.

### UI Feature 02 - Role-Aware App Shell And Navigation

Goal:

Make role switching, active view, and global shell navigation clear without
changing access rules.

Screens affected:

- Shared app shell
- Account menu
- Contributor/Presenter/Admin entry states

Confirmed requirements:

- A user can be Contributor, Presenter, Admin, or any combination.
- User menu in the top right is the view switcher.
- Contributor View shows only assigned partners.
- Presenter View can see all partners.
- Admin Console appears only for Admin users.

Scope:

- Preserve top-right account switcher behavior.
- Make active view discoverable.
- Show only available views.
- Keep current product name placement.
- Ensure sign-out remains easy to find.

Implementation targets:

- `apps/web/src/features/shell/AccountViewShell.tsx`
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Bhumik can switch between Contributor View and Presenter View.
- Admin can access Admin Console.
- Non-admins do not see Admin Console.
- The active view is visible without requiring guesswork.

### UI Feature 03 - Admin Console Navigation And Control Plane Frame

Goal:

Create a coherent Admin View shell before polishing individual admin modules.

Screens affected:

- Admin Console
- Admin module tabs

Confirmed requirements:

- Admin modules include Team, Partners, Knowledge Upload, Global Integrations,
  and Source Approvals in the current app.
- Admin is the control plane for users, partners, integrations, and source
  approvals.
- Admin does not edit rulebooks.

Open decisions:

- Gate 6: whether Knowledge Upload remains visible.

Scope:

- Standardize admin page header, module tabs, active state, card/list styling,
  and narrow/desktop layout behavior.
- Keep admin pages compact and operational.
- Do not add Admin Health/Audit unless later promoted.

Implementation targets:

- `apps/web/src/features/shell/AccountViewShell.tsx`
- Admin panel components
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Admin modules feel like one console instead of unrelated panels.
- Tab labels match product terms.
- Hidden/backlog modules are not shown if not approved.

### UI Feature 04 - Admin Team And Partners Parity

Goal:

Bring Admin Team and Partners screens close to the previous approved UI while
respecting the new role and assignment model.

Screens affected:

- Admin Team
- Admin Partners

Confirmed requirements:

- Team screen name remains Team.
- Admin can create/edit/deactivate/reactivate users.
- Roles are Contributor, Presenter, Admin.
- A person can hold multiple roles.
- Admin can create/edit/archive partners.
- Each partner has one contributor owner.
- No invitation UI for now.

Open decisions:

- Gate 2: password set/reset UI.

Scope:

- Improve table density, role checkboxes, role pills, active/deactivated pills,
  add/edit forms, and partner assignment display.
- Keep last-admin protection behavior visually understandable.
- If Gate 2 chooses no password UI, do not add password fields.

Implementation targets:

- `apps/web/src/features/admin/AdminTeamPanel.tsx`
- `apps/web/src/features/admin/AdminPartnersPanel.tsx`
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Admin can scan user roles quickly.
- Admin can understand which contributors own which partners.
- No password or invitation controls appear unless explicitly approved.

### UI Feature 05 - Contributor Partner Selection And Dashboard Shell

Goal:

Make the contributor entry flow and partner-scoped workspace match the intended
product flow.

Screens affected:

- Contributor Partner Selection
- Contributor Dashboard Shell

Confirmed requirements:

- Contributors with many partners see partner selection.
- Contributors with one partner land directly in Contributor View.
- Contributor dashboard defaults to Pending Updates.
- Final contributor sections are:
  - Pending Updates
  - Partner Metadata
  - Approved Updates
  - Connected Sources
- Partner switcher, cycle picker, search, and account menu stay available.

Scope:

- Polish partner cards.
- Remove technical slot/internal naming from cards.
- Standardize selected partner header.
- Keep partner switcher behavior.
- Make tab ordering and counts clear.

Implementation targets:

- `apps/web/src/features/contributor/ContributorPartnerSelectionPanel.tsx`
- `apps/web/src/features/contributor/ContributorDashboardShell.tsx`
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Contributor sees only assigned partners.
- Multi-partner and single-partner flows behave correctly.
- Pending Updates is the default working tab.
- Tab counts do not shift layout.

### UI Feature 06 - Contributor Pending, Approved, And Manual Updates

Goal:

Make the update review workflow visually match the old approved interaction
while preserving the new backend lifecycle.

Screens affected:

- Pending Updates
- Approved Updates
- Manual Add Update

Confirmed requirements:

- Pending Updates show newest first.
- Pending rows show update text, source type, source link when applicable.
- No source excerpt.
- Contributor can Approve, Edit, and Reject/Dismiss.
- Editing is optional and stores only latest text.
- Approved Updates are read-only and immutable.
- Manual updates enter Pending Updates first.
- Manual update month is approval month.
- No visible classification fields.
- No workstream/topic tags.

Scope:

- Match old table/row visual style as closely as possible.
- Keep source chips for Contributor View.
- Keep search, source filter, and month/cycle filter.
- Make destructive bulk actions less prominent and confirm before executing.
- Keep manual add update separate from Connected Source setup.

Implementation targets:

- `apps/web/src/features/contributor/ContributorUpdatesPanel.tsx`
- `apps/web/src/features/contributor/ManualUpdateForm.tsx`
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Pending review feels like the previous product flow.
- Approved Updates have no edit/delete affordance.
- Source-generated rows do not expose raw source content.
- Manual update creation is clearly not a Connected Source flow.

### UI Feature 07 - Partner Metadata And Resource Links

Goal:

Bring Partner Metadata close to the previous approved screen while resolving the
Resource Links simplification.

Screens affected:

- Partner Metadata tab

Confirmed requirements:

- Only assigned contributors can edit metadata.
- Metadata is saved by selected month/cycle.
- Contributor clicks Save Metadata to publish latest monthly snapshot.
- No intermediary version history.
- Status colors are Green, Amber, Red.
- Key Risks & Issues uses tabular format:
  - item number
  - description
  - go-to-green action
  - severity
  - assigned owner
  - due date
  - ramification
  - remove action
- Resource Links fields are Title, URL, optional Description.
- Resource Links are convenience links, not training/source ingestion settings.

Open decisions:

- Gate 5: whether to keep Why This Partner and Execution Timeline.

Scope:

- Restyle metadata sections, status selector, text fields, goals, risk table,
  add/remove rows, save bar, dirty state, validation, and save confirmation.
- Simplify Resource Links.
- Add origin/disabled visual treatment only if supported by data and confirmed.

Implementation targets:

- `apps/web/src/features/contributor/ContributorPartnerMetadataPanel.tsx`
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Metadata screen matches the intended old layout closely.
- Resource Links no longer show category, featured, or commit-to-training UI.
- Save state is obvious.
- Long risk/resource rows remain readable.

### UI Feature 08 - Contributor Connected Sources

Goal:

Polish the contributor-owned Connected Sources tab as the place where
partner-specific source requests are managed.

Screens affected:

- Contributor Connected Sources
- Partner Files section if retained

Confirmed requirements:

- Connected Sources are separate from Resource Links.
- Contributor can request:
  - Slack Channel
  - Jira Issue
  - SharePoint File
  - Confluence Page
  - GitHub Repository
  - GitHub Issue
  - GitHub Pull Request
- Contributor never sees global secrets.
- Contributor does not run source access tests before submission.
- Contributor does not provide rulebook/free-text processing guidance.
- Contributor UI should not mention polling.
- Slack requires channel name, channel ID, and bot-invited confirmation.
- Jira/SharePoint/Confluence/GitHub use URL-based source requests.
- Slack does not create Resource Links.

Open decisions:

- Gate 7: contributor status label depth.
- Gate 8: whether to wait for Figma design.
- Gate 6: Partner Files visibility.

Scope:

- Replace current scaffolding layout with the final design direction.
- Make request forms source-specific but compact.
- Show clear source status table.
- Make edit/resubmit/pause/resume/archive behavior understandable.
- Avoid overlapping with Resource Links.

Implementation targets:

- `apps/web/src/features/contributor/ContributorConnectedSourcesPanel.tsx`
- `apps/web/src/features/contributor/ContributorUploadsPanel.tsx`
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Contributor can request each source type without seeing admin/global fields.
- Rejected source can be corrected and resubmitted if supported.
- Active source pause/resume is clear if visible.
- Archived/disabled behavior does not imply data deletion.

### UI Feature 09 - Admin Global Integrations

Goal:

Finalize the admin-owned integration credential and readiness screen.

Screens affected:

- Admin Global Integrations

Confirmed requirements:

- Admin configures global credentials for:
  - Slack
  - Jira
  - SharePoint / Microsoft Graph
  - Confluence
  - GitHub
- Saved secret values are never displayed.
- Admin can save/rotate credentials.
- Admin can test readiness.
- Admin can enable/disable integrations.
- Contributor-specific configuration does not belong here.
- No Slack channel IDs, Jira issue URLs, SharePoint file URLs, Confluence page
  URLs, GitHub repo/issue/PR URLs, polling settings, or rulebook editing.

Open decisions:

- Gate 8: whether to wait for Figma design.

Scope:

- Polish integration cards/details.
- Show status, required fields, configured/not configured state, webhook URL,
  test readiness, enabled/disabled, and recent health.
- Make local readiness vs external API validation clearly worded.
- Keep public HTTPS webhook blockers visible in docs, not as alarming UI unless
  needed.

Implementation targets:

- `apps/web/src/features/admin/AdminIntegrationsPanel.tsx`
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Admin can understand what is configured and what still needs external setup.
- Secret fields never echo saved values.
- Webhook URL is easy to copy/read.
- Global setup is visually separate from source approvals.

### UI Feature 10 - Admin Connected Source Approvals

Goal:

Finalize the admin approval workbench for contributor-requested sources.

Screens affected:

- Admin Source Approvals

Confirmed requirements:

- Admin queues:
  - Needs Review
  - Attention
  - Active
  - Rejected
  - All
- Admin can test access readiness.
- Admin can approve and activate a pending source only when global integration
  is enabled and access readiness passes.
- Admin can reject.
- Admin can mark Needs Access Setup.
- Admin can disable an active source.
- Contributor sees resulting status.
- Exact duplicates are flagged or rejected; near duplicates remain visible.
- Admin sees technical status/errors; contributor does not.

Open decisions:

- Gate 8: whether to wait for Figma design.

Scope:

- Polish queue tabs, source table, detail panel/drawer, review note, technical
  status, action buttons, and status transitions.
- Make global integration gating clear.
- Keep rejection reason optional.

Implementation targets:

- `apps/web/src/features/admin/AdminSourceApprovalsPanel.tsx`
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Admin can process a pending request end to end.
- The current selected source is visually obvious.
- Disabled global integrations block approval in a clear way.
- Contributor-facing status is updated after admin action.

### UI Feature 11 - Presenter Workspace

Goal:

Make Presenter View read-only, analysis-forward, and visually aligned with the
legacy presenter intelligence screen.

Screens affected:

- Presenter Approved Updates
- Presenter Partner Metadata
- Executive Summary
- Decision Board
- Draft Email
- Reports area if promoted

Confirmed requirements:

- Presenter sees all partners by default.
- Default month/cycle is current calendar month.
- Presenter can filter by partner and month/cycle.
- Presenter can view Approved Updates.
- Presenter can view Partner Metadata only for a selected single partner.
- Presenter cannot edit metadata, updates, or reports.
- Analysis remains separate from metadata and approved updates.
- Executive Summary and Decision Board use Approved Updates only for v1.
- Draft Email uses Approved Updates and developer-owned rulebook.
- PowerPoint export is out.

Open decisions:

- Gate 3: Word report UI.
- Gate 4: Ask AI.

Scope:

- Match old presenter feed/read-only tone.
- Make Executive Summary and Decision Board first-class modules.
- Keep Partner Metadata visibly separate from analysis.
- Position Generate Email Draft cleanly.
- Add artifact/download area only if Word/email download is confirmed for this
  UI pass.

Implementation targets:

- `apps/web/src/features/presenter/PresenterWorkspacePanel.tsx`
- `apps/web/src/app/globals.css`

Acceptance criteria:

- Presenter can understand the difference between raw approved information and
  generated analysis.
- All Partners default is clear.
- Single-partner metadata behavior is clear.
- No edit actions appear in Presenter View.
- No Export Deck/PowerPoint action appears.

### UI Feature 12 - Empty, Error, Loading, Permission, And Data-Quality States

Goal:

Make the product feel robust when data is missing, integrations are incomplete,
or users lack access.

Screens affected:

- All role views.

Scope:

- Empty partner list.
- Empty pending updates.
- Empty approved updates.
- Empty metadata.
- Empty connected sources.
- Empty admin queues.
- Empty presenter analysis.
- Login failure.
- Permission denied.
- Global integration disabled.
- Source approval blocked.
- Source request duplicate.
- Save success/error.
- Long-running draft email generation.

Acceptance criteria:

- No screen appears broken when there is no data.
- Errors explain next action without exposing secrets or raw source content.
- Permission failures are clear and not noisy.

### UI Feature 13 - Browser Walkthrough And Visual Regression Pass

Goal:

Validate the UI as a real product flow after each feature group, not only as
compiled React code.

Scope:

- Test with Admin login.
- Test with Bhumik Patel contributor/presenter login.
- Walk every role.
- Click every tab and major button.
- Create temporary data where needed.
- Verify no changes are written to `Gold/`.
- Capture screenshots for:
  - login
  - admin modules
  - contributor partner selection
  - contributor pending/approved/manual update
  - contributor metadata
  - contributor connected sources
  - presenter workspace
  - empty states
  - key mobile/tablet breakpoints if Gate 9 requires it

Acceptance criteria:

- `pnpm --dir apps/web typecheck` passes.
- `pnpm --dir apps/web build` passes.
- Backend tests still pass when UI work touches shared contracts.
- Docker web/API run locally.
- Browser screenshots are reviewed for overlap, overflow, broken tables, and
  mismatched states.

## 7. Recommended Implementation Grouping

To avoid one large UI rewrite, implement in these groups:

1. Group A - Foundation and navigation
   - UI Feature 00
   - UI Feature 01
   - UI Feature 02

2. Group B - Admin parity
   - UI Feature 03
   - UI Feature 04
   - UI Feature 09
   - UI Feature 10

3. Group C - Contributor parity
   - UI Feature 05
   - UI Feature 06
   - UI Feature 07
   - UI Feature 08

4. Group D - Presenter parity
   - UI Feature 11

5. Group E - Hardening and walkthrough
   - UI Feature 12
   - UI Feature 13

Recommended order:

1. Resolve decision gates.
2. Build Group A.
3. Build Contributor and Admin in whichever order has the clearest design
   reference. If Figma designs for Connected Sources/Admin screens are not
   ready, do the reusable Contributor metadata/update parity first.
4. Build Presenter parity after enough approved update data exists.
5. Run full browser walkthrough and screenshot review.

## 8. Explicit Non-Goals For This UI Pass

Unless a decision gate promotes them, do not build:

- SSO UI.
- OTP or magic-link login.
- Self-service signup.
- Self-service forgot password.
- PowerPoint export.
- Admin rulebook editing.
- Contributor free-text rulebook guidance.
- Workstream admin UI.
- Polling/sync controls.
- Raw Slack message display.
- Raw Jira/Confluence/GitHub source content display.
- Presenter report editing.
- Approved update editing/deletion.
- Full mobile-first redesign.
- AWS deployment screens.

## 9. Questions For Product Decision

Please answer these before UI implementation starts:

1. Landing page: keep it, remove it, or keep layout with updated copy?
2. Admin passwords: keep no password UI, or add Admin set/reset password?
3. Word report: include UI now, or keep it out of this pass?
4. Presenter Ask AI: hide it, placeholder it, or promote it?
5. Metadata: keep Why This Partner and Execution Timeline, or remove them?
6. Knowledge Upload / Partner Files: keep visible, or hide for now?
7. Contributor statuses: simple Pending/Active/Rejected only, or broader
   operational statuses?
8. Pending Figma screens: wait for Figma, or polish the current functional UI?
9. Mobile: desktop/tablet-first with usable mobile, or fully polished mobile?

## 10. Success Definition

The UI pass is complete when:

- Every visible screen matches a confirmed product purpose.
- Legacy-approved visual patterns are reused where requested.
- Old concepts do not leak into the product:
  - workstreams
  - polling
  - PPT export
  - signup/reset flows
  - admin rulebook editing
  - source excerpts
- Contributor, Presenter, and Admin can complete their core workflows.
- The UI is no longer "functional scaffolding"; it feels like a coherent
  product-shaped internal platform.
