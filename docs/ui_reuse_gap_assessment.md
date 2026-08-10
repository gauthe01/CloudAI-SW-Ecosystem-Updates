# UI Reuse And Gap Assessment

## 1. Purpose

This is a UI-only audit of the current local app at `http://localhost:8000`.

The audit focused on how the screens look and behave, not backend architecture. Screenshots were captured in:

`docs/ui_audit_screenshots/`

The contact sheet is:

`docs/ui_audit_screenshots/contact_sheet.png`

## 2. Screenshot Coverage

Captured areas:

- Landing page
- Login
- Forgot password
- Signup
- Admin home
- Admin partners list
- Admin partner add/edit forms
- Admin team list
- Admin team add/edit forms
- Admin knowledge upload
- Admin integrations overview
- Admin Slack integration detail
- Admin Jira integration detail
- Partner selection
- Account menu role switching
- Contributor pending updates
- Contributor approved updates
- Contributor filters/search
- Contributor pending edit mode
- Contributor partner switcher
- Contributor cycle picker
- Contributor metadata
- Metadata add-row controls
- Manual add update
- File add update
- Slack add update
- Jira add update
- Presenter intelligence
- Presenter period picker
- Presenter search
- Presenter email modal
- Presenter export deck modal
- Presenter AI panel
- Smart Analysis page
- Mobile contributor pending
- Mobile contributor metadata
- Mobile presenter intelligence
- Mobile admin home
- Active-user login matrix

## 3. Active User UI Matrix

The UI was tested against active users in the local DB.

| User | Expected role shape | UI result |
|---|---|---|
| `admin@arm.com` | Admin + presenter | Login works, lands on Admin console |
| `sameer.nori@arm.com` | Contributor + presenter | Login works, lands on Partner Selection |
| `jason.dudek@arm.com` | Contributor + presenter | Login works, lands directly on assigned partner Contributor View |
| `yan.fisher@arm.com` | Contributor + presenter | Login works, lands on Partner Selection |
| `bhumik.patel@arm.com` | Contributor + presenter | Active user, but pilot password failed |
| `browser.signup.1782096910290@arm.com` | Presenter | Active user, but pilot password failed |
| `gaurikrishnamoorthy.thevar@arm.com` | Presenter | Active user, but pilot password failed |
| `team.member.edited@example.com` | Contributor | Active user, but pilot password failed |

UI implication:

- The admin-created-user pilot flow is not visually complete unless every active user has an admin-set password state.
- Failed login messaging is understandable, but the user has no way to know whether they are missing access, have the wrong password, or need an admin reset.
- For the new plan, the login UI should remove signup/forgot-password if users are admin-created and passwords are admin-managed.
- Admin Team UI needs a clear password-set/reset action if we are not using OTP or self-service reset.

## 4. Overall UI Verdict

The current UI is more valuable as a product reference than as implementation code.

Reuse the interaction ideas and visual patterns:

- Dark top bar.
- Partner switcher.
- Account menu role switcher.
- Contributor pending/approved review table.
- Source chips.
- Metadata section layout.
- Risk table.
- Resource Links table.
- Admin module cards.
- Admin team/partner CRUD tables.
- Presenter all-partner read-only feed.
- AI side panel pattern.

Do not carry the UI forward as-is:

- The Jinja pages are too large and inconsistent.
- Some product concepts are outdated.
- Several screens are still prototype/marketing-shaped.
- Some flows conflict with the new PRD.
- Mobile behavior is not polished enough.
- Admin integrations and Connected Sources are not separated cleanly.

## 5. What Can Be Reused Visually

### 5.1 Contributor View

Reusable:

- Top bar with product name, selected partner, user menu, and sign-out.
- Partner dropdown/switcher.
- Month/cycle selector.
- Search box.
- Pending Updates / Approved Updates tab pattern.
- Count badges on tabs.
- Source chips on update rows.
- Row actions: Approve, Edit, Dismiss.
- Inline edit mode for pending update text.
- Empty state for no pending updates.
- Approved-update read-only row style.
- Filter popover with source filters.

Good UI behaviors:

- Contributor with one partner lands directly on Contributor View.
- Contributor with many partners sees a partner selection grid.
- Account menu allows contributor/presenter switching.
- Pending update edit mode is visible and understandable.
- Source chips are visually scannable.

Needed changes:

- Add a fourth primary tab/section: `Connected Sources`.
- Default Contributor View should be `Pending Updates`.
- Hide or remove Workstream-based UI concepts.
- Remove source excerpt/evidence display from normal contributor UI if PRD says no source excerpt.
- Replace `+ Add update` source picker with a simpler manual-update action plus separate Connected Sources setup.
- Make destructive actions like `Dismiss all` less prominent and require confirmation.
- Keep partner selection, but treat it as a switcher state, not a separate product destination.

### 5.2 Partner Metadata

Reusable:

- Status segmented control.
- Metadata form grouped into sections.
- Business Priority, Highlights / Status, Goals cards.
- Key Risks & Issues table.
- Add/remove row controls.
- Save Metadata button.

Good UI behaviors:

- Status colors Green/Amber/Red are clear.
- Metadata form is easy to scan on desktop.
- Add buttons create new rows inline.
- The Key Risks & Issues row matches the user-provided desired table shape closely.

Needed changes:

- Remove `Why this partner` unless we explicitly keep it; it is not in the final metadata list.
- Remove `Execution timeline` unless we explicitly keep it; it was not part of the final agreed metadata set.
- Simplify Resource Links to `Title + URL + optional Description`.
- Remove `Featured` and possibly `Category` from Resource Links unless we decide link type is still needed.
- Add disabled/archived visual state for Resource Links auto-created from archived Connected Sources.
- Add validation states that are clearer when rows are partially filled.
- Consider sticky save/dirty-state behavior because metadata is long.

### 5.3 Presenter View

Reusable:

- All Partners default view.
- Top partner selector.
- Month selector.
- Search.
- Approved-update feed grouped by date and partner.
- Read-only tone.
- AI side panel pattern.
- Email modal pattern.
- Analysis view entry point.

Good UI behaviors:

- Presenter View can show all partners, not just assigned partners.
- Account menu correctly switches from Contributor View to Presenter View.
- Approved updates are visually separated from contributor review controls.
- AI panel is useful as a sidecar instead of replacing the intelligence feed.

Needed changes:

- Remove `Export deck` from v1 because PowerPoint is out of scope.
- Replace `Export deck` with `Download Word Report`.
- Keep `Draft email`, but rename/position as `Generate Email Draft` or similar.
- Add explicit selected-partner subset controls for report/email/analysis.
- Ensure `Executive Summary` and `Decision Board` are clearly visible as analysis modules, not hidden behind generic `Analysis view`.
- Keep raw Partner Metadata and Approved Updates separate from analysis.
- Add a clear downloadable artifact area for Word report and email draft.

### 5.4 Admin View

Reusable:

- Admin console card layout.
- Partner management table/form.
- Team management table/form.
- Role checkboxes.
- Last admin lock concept.
- Integration cards.
- Secret save/test UI pattern.

Good UI behaviors:

- Admin sections feel like a control plane.
- Team add/edit UI is reasonably structured.
- Partner add/edit UI is familiar.
- Integration status cards are understandable.

Needed changes:

- Add `Connected Source Approvals` as a first-class admin module.
- Add global integration cards for Jira, Slack, SharePoint, Confluence, GitHub.
- Remove or hide `Knowledge Upload` if not part of immediate v1 admin scope, or rename it according to the PRD.
- Remove or hide Assistant/rulebook UI because rulebooks are developer-owned for now.
- Remove or hide Templates/Platform Settings if not implemented.
- Add admin password set/reset controls for users.
- Clarify role assignment: contributor, presenter, admin can be combined.
- Clarify partner assignment within Team UI.
- Integration UI should distinguish:
  - global secret/config
  - enabled/disabled/test state
  - contributor source approval queue
  - health/failure status

## 6. Major UI Gaps Against The New PRD

### 6.1 Missing Contributor Connected Sources

Current UI has:

- Add Update source cards: Manual, Files, Slack, Jira.
- Admin source mappings/integrations.

New PRD needs:

- Contributor View section named `Connected Sources`.
- Contributor can request/configure partner-specific sources:
  - Slack channel name
  - Slack channel ID
  - bot invited confirmation checkbox
  - Jira issue URL
  - SharePoint file URL
  - Confluence page URL
  - GitHub repo/issue/PR URL
- Contributor sees statuses:
  - Pending
  - Active
  - Rejected
  - Disabled/Archived
- Contributor can pause/resume/archive/resubmit where allowed.

This is the biggest missing UI area.

### 6.2 Admin Connected Source Approvals

Current UI has admin integrations and source mappings, but not the new approval workflow.

New PRD needs:

- Admin queue of contributor source requests.
- Detail drawer/page for each request.
- Approve / Reject / Need Access Setup actions.
- Test connection/access before Active.
- Rejection visible to contributor.
- Duplicate exact source detection.
- Global integration disabled state blocks approval.

### 6.3 Auth UI Does Not Match Pilot Decision

Current UI has:

- Login.
- Forgot password.
- Signup.
- Keep me signed in.

New PRD says:

- Admin creates users.
- Admin sets password for pilot.
- No OTP.
- No self-signup.
- SSO later replaces password login.

Needed UI:

- Remove signup.
- Remove forgot password or change it to "Contact admin".
- Admin Team screen needs `Set password` / `Reset password`.
- Login error should distinguish inactive/no access vs wrong password where appropriate.

### 6.4 Resource Links Still Mix Old Concepts

Current metadata Resource Library has:

- Category/type dropdown.
- Title.
- URL.
- Description.
- Featured checkbox.

New PRD says:

- Resource Links are convenience links.
- Fields: title, URL, optional description.
- Any link is allowed.
- No commit-to-training in Resource Links.
- If added from Connected Source, it remains visible but disabled/archived if source archived.

Needed UI:

- Simplify Resource Links.
- Add origin indicator: manual vs connected source.
- Add disabled/archived state.
- Do not expose training settings there.

### 6.5 Presenter Report Actions Need New Shape

Current Presenter UI has:

- Ask AI.
- Analysis view.
- Export deck.
- Draft email.

New PRD needs:

- Executive Summary.
- Decision Board.
- Word monthly report download.
- Executive email draft download.
- No report editing.
- No PowerPoint for now.

Needed UI:

- Replace `Export deck`.
- Add `Download Word Report`.
- Keep/generate email draft.
- Make Executive Summary and Decision Board top-level analysis choices.
- Show last generated artifact state.

## 7. Inconsistencies And UX Issues Found

### 7.1 Landing Page Is No Longer Product-Appropriate

The landing page is marketing-style and mentions:

- Google Drive sync.
- Nightly automatic sync.
- PPT generation.
- Google Meet/Gmail/Notion/Zoom.

This conflicts with the current product plan.

Recommendation:

- For the rebuilt app, do not use a marketing landing page.
- Authenticated users should land directly in their default view.
- Login page can be the first unauthenticated screen.

### 7.2 Account Role Switcher Works But Is Easy To Miss

The user menu in the top right is the only way to switch Contributor/Presenter views.

Recommendation:

- Keep it.
- Make the active view label more visible.
- Consider showing `Contributor View` / `Presenter View` in the top bar next to the user name.
- If a user has both roles, make switcher discoverability higher.

### 7.3 Partner Selection Is Useful But Should Be Integrated

The partner selection grid is valuable for contributors with many partners.

Recommendation:

- Keep it as a contributor landing/partner switcher.
- Remove technical partner slots from prominent card text unless needed for admin/debug.
- The new UI should use partner names, counts, and statuses, not internal slot names.

### 7.4 Some Active Users Cannot Login

Several active users failed with the pilot password.

Recommendation:

- Treat this as a product/admin UI gap.
- Admin must be able to see whether a user has a password set.
- Admin must be able to set/reset the pilot password.

### 7.5 Password Label Accessibility Ambiguity

Automated label targeting matched both the Password field and Forgot Password link.

Recommendation:

- Change the forgot link aria label to avoid conflicting with field label, or ensure the input has a unique label association.

### 7.6 Mobile Is Functional But Not Product-Polished

Mobile captures show the screens stack, but long tables and dense top bars are not polished.

Recommendation:

- For v1, optimize for desktop/tablet if that reflects actual usage.
- Still ensure mobile is usable:
  - top bar wraps cleanly
  - metadata rows do not become unreadable
  - presenter feed remains readable
  - admin cards do not become awkward narrow columns

### 7.7 Admin Integrations Overview Has Layout Problems

The integrations overview appeared narrow/left-compressed in screenshot capture.

Recommendation:

- Rebuild as responsive cards using consistent page shell.
- Use a table/list for health details.
- Make integration statuses explicit: Not Configured, Needs Test, Connected, Disabled, Failed.

### 7.8 Add Update Flow Is Overloaded

Current Add Update screen handles:

- Manual note.
- Files upload.
- Slack source.
- Jira source.

New plan separates:

- Manual update.
- Connected source setup.
- Source-generated pending updates.

Recommendation:

- Keep manual update flow.
- Move Slack/Jira/SharePoint/Confluence/GitHub setup to Connected Sources.
- Keep file upload only if knowledge/manual upload is in v1.

## 8. Recommended New Client Navigation

### Contributor View

Primary sections:

- `Pending Updates`
- `Partner Metadata`
- `Approved Updates`
- `Connected Sources`

Secondary controls:

- Partner switcher.
- Month/cycle picker.
- Search.
- Source filter.

Primary actions:

- `Add Manual Update`
- `Save Metadata`
- `Request Connected Source`

### Presenter View

Primary sections:

- `Approved Updates`
- `Partner Metadata`
- `Executive Summary`
- `Decision Board`
- `Reports`

Primary actions:

- `Generate Word Report`
- `Download Word Report`
- `Generate Email Draft`
- `Download Email Draft`

### Admin View

Primary modules:

- `Users`
- `Partners`
- `Partner Assignments`
- `Global Integrations`
- `Connected Source Approvals`
- `Integration Health`
- `Audit Logs`

Optional/backlog modules:

- `Knowledge Upload`
- `Rulebooks`
- `Templates`
- `Platform Settings`

## 9. UI Reuse Priority

Reuse first:

- Contributor update list.
- Pending edit interaction.
- Metadata layout.
- Risk table.
- Account role switcher.
- Partner selector/switcher.
- Presenter feed.
- Admin team and partner tables.

Modify heavily:

- Resource Links.
- Add Update.
- Admin integrations.
- Presenter report actions.
- Auth pages.

Build new:

- Contributor Connected Sources.
- Admin Connected Source approval queue.
- Integration health dashboard.
- Report artifacts/download screen.
- Executive Summary and Decision Board modules as first-class presenter surfaces.

Remove/hide for v1:

- Signup.
- Forgot password self-service.
- PowerPoint export.
- Assistant/rulebook admin UI.
- Workstream admin UI.
- Marketing landing page.
- Polling/sync language in UI.

## 10. Bottom Line

The current UI is a strong visual prototype for contributor review, metadata editing, admin basics, and presenter intelligence. It should guide the rebuilt React UI.

But the new client should not copy the current UI one-for-one. The new product model requires a clearer split:

- Contributor edits partner metadata and reviews updates.
- Contributor manages partner-specific Connected Sources.
- Admin manages global integrations and source approvals.
- Presenter consumes approved information and generated analysis/artifacts.

The largest missing UI is Connected Sources. The largest UI mismatch is authentication/self-signup/reset. The largest cleanup is removing old polling/workstream/PPT language from user-facing screens.

