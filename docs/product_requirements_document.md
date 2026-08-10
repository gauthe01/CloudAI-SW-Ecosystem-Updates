# Product Requirements Document

Product: Cloud AI Software Ecosystem Updates
Version: PRD v1
Date: 2026-08-06
Status: Draft for product review

## 1. Purpose

The product is a software ecosystem updates and reporting platform for managing
external partner activity, turning trusted source activity into contributor
reviewed updates, and generating monthly reporting outputs.

The product should help internal teams understand what matters across partners:
decision-ready signals, partner health, source-backed updates, and monthly
reporting. It should not simply collect activity. It should help users identify
what needs attention and preserve approved partner knowledge over time.

## 2. North Star

The north-star priorities, from highest to lowest, are:

1. Live software ecosystem updates
2. Monthly partner reporting
3. Partner memory / source of truth
4. Presenter preparation

Live software ecosystem updates is the primary purpose. Reporting, memory, and
presenter preparation are downstream outcomes of trusted live intelligence.

## 3. Live Software Ecosystem Updates Definition

Live Software Ecosystem Updates should prioritize:

1. Decision-ready signals
2. Partner health
3. Partner activity

The product should surface what matters, not simply display everything that
happened.

Decision-ready signals include:

- Risks and blockers
- Asks or decisions needed
- Upcoming deadlines
- Important partner movement that may affect monthly reporting

Partner health includes:

- Current status
- Business priority
- Goals
- Key risks and issues
- Current context maintained by the assigned contributor

Partner activity includes:

- Approved updates generated from connected sources
- Approved manual updates
- Source-backed activity from Jira, Slack, SharePoint, Confluence, and GitHub

## 4. Core Product Principles

1. Source-backed intelligence
   - Source-generated updates should come from a known source.
   - One update comes from one source only.
   - Multiple sources create multiple updates.
   - One source may create multiple updates when there are multiple meaningful events.

2. Human review before official use
   - Source-generated updates must become Pending Updates first.
   - Manual updates must also become Pending Updates first.
   - Only the assigned contributor can approve updates for their partner.

3. Approved Updates are the official truth
   - Approved Updates feed live intelligence.
   - Approved Updates feed monthly Word reports.
   - Approved Updates feed executive email drafts.
   - Approved Updates feed partner memory/training.
   - Approved Updates are immutable after approval.

4. Partner metadata is manually maintained
   - Partner metadata is entered by the assigned contributor.
   - AI should not generate or modify metadata fields.
   - Metadata is visible in Presenter View, but does not feed reports or analysis for now.

5. Rulebooks are developer-owned for now
   - Extraction behavior is governed by developer-owned rulebooks.
   - Executive email behavior is governed by a developer-owned rulebook.
   - Admins do not edit rulebooks in the UI.
   - Contributors do not provide processing guidance for now.

6. Admin prepares system capabilities; contributors configure partner sources
   - Admin owns global integration configuration.
   - Contributor owns partner-specific Connected Source requests.
   - Admin approval and system testing are required before sources become active.

7. Keep the first product-shaped pass simple
   - Avoid report editing for now.
   - Avoid visible classification fields for now.
   - Avoid edit histories for update drafts for now.
   - Avoid polling as a product concept.

## 5. Primary Users And Roles

The product has three role capabilities:

- Contributor
- Presenter
- Admin

A user can have multiple capabilities. For example, a person can be both a
Contributor and a Presenter.

### 5.1 Contributor

A Contributor is responsible for one or more assigned partners.

Contributor assignment model:

- One contributor can own many partners.
- Each partner has exactly one assigned contributor.
- Admin assigns contributors to partners.

Contributor permissions:

- Can see and edit only assigned partners in Contributor View.
- Can edit Partner Metadata for assigned partners.
- Can manage Resource Links for assigned partners.
- Can submit Connected Source requests for assigned partners.
- Can pause/resume their own active Connected Sources.
- Can approve, edit, or reject Pending Updates for assigned partners.
- Can manually create Pending Updates.
- Cannot approve updates for unassigned partners.
- Cannot edit or delete Approved Updates.
- Cannot configure global integrations.
- Cannot edit rulebooks.

### 5.2 Presenter

A Presenter has global read-only access to software ecosystem intelligence.

Presenter permissions:

- Can access Presenter View.
- Can see all partners in Presenter View.
- Can view Partner Metadata as current context.
- Can view Approved Updates.
- Can view separate analysis sections.
- Can generate monthly Word reports.
- Can generate executive email drafts.
- Cannot edit Partner Metadata.
- Cannot approve Pending Updates.
- Cannot edit Approved Updates.
- Cannot curate or edit report contents for now.
- Cannot configure integrations.

### 5.3 Admin

Admin is the product control role.

Admin permissions:

- Create and manage users.
- Assign contributor capability.
- Assign presenter capability.
- Create partners.
- Edit basic partner identity.
- Assign one contributor owner per partner.
- Archive partners.
- Configure global integration credentials/settings.
- Test global integrations.
- Review and approve/reject Connected Source requests.
- View detailed technical errors/status for integration setup and source testing.

Admin restrictions:

- Admin does not edit developer-owned rulebooks.
- Admin does not edit Partner Metadata.
- Admin does not approve partner Pending Updates.
- Admin rejection of Connected Sources does not require a reason.
- For v1, Admin capability itself should be protected by bootstrap/config rather
  than casually assigned in the app.

## 6. Authentication And Access

### 6.1 Pre-SSO Login

Before ARM SSO is available:

- Admin creates users with name and email.
- Admin assigns contributor/presenter capabilities.
- Admin assigns partner ownership for contributors.
- Users log in with email plus a shared developer/configured default password.
- The default password is shared outside the app by Admin.
- The app does not display the default password.
- The default password approach is temporary for a hosted pilot.

### 6.2 SSO Future State

When SSO arrives:

- Password login should be disabled completely.
- SSO identifies the user.
- The app still controls role/capability assignment and partner ownership.

### 6.3 First Admin

The first Admin should be bootstrapped from environment/config.

## 7. Key Terminology

Use these terms consistently in the UI and documentation.

| Term | Meaning |
| --- | --- |
| Contributor View | Contributor-facing workspace for assigned partners. |
| Presenter View | Read-only presenter workspace across all partners. |
| Admin View | Administrative workspace for users, partners, integrations, and source approvals. |
| Partner Metadata | Contributor-maintained current partner snapshot. |
| Resource Links | Convenience links stored on the partner metadata page. |
| Connected Sources | Contributor-requested sources that can generate Pending Updates after Admin approval and system testing. |
| Pending Updates | Pre-approval updates awaiting assigned contributor review. |
| Approved Updates | Contributor-approved official updates. |
| Source Item | Backend/source event or source content used to generate Pending Updates. |

## 8. Product Components

Main product components:

1. Contributor View
2. Presenter View
3. Admin View
4. Partner Metadata
5. Resource Links
6. Connected Sources
7. Pending Updates
8. Approved Updates
9. Integration setup
10. Monthly Word report generation
11. Executive email draft generation
12. Executive Summary analysis
13. Decision Board analysis

## 9. Partner Model

Each partner has:

- Partner identity
- Assigned contributor
- Partner Metadata
- Resource Links
- Connected Sources
- Pending Updates
- Approved Updates

Partner creation and ownership:

- Admin creates partners.
- Admin edits basic partner identity.
- Admin assigns exactly one contributor owner.
- Admin can archive a partner.

Basic partner identity includes:

- Partner name
- Website
- Logo/color or similar identity metadata, if available
- Active/inactive/archive status

## 10. Contributor View

### 10.1 Contributor Navigation

Contributor flow:

1. Contributor opens Contributor View.
2. Contributor selects one assigned partner using a partner selector.
3. Contributor works inside that partner context.

The default first section after selecting a partner should be Pending Updates.

Contributor View sections:

1. Pending Updates
2. Partner Metadata
3. Approved Updates
4. Connected Sources

Partner Metadata includes Resource Links.

### 10.2 Contributor Visibility

In Contributor View:

- Contributor can see and edit only assigned partners.
- Contributor cannot see or edit unassigned partners in Contributor View.

If a user also has Presenter capability:

- They can use Presenter View to see all partners read-only.
- Their Contributor View remains limited to assigned partners.

## 11. Partner Metadata

### 11.1 Purpose

Partner Metadata is the current partner snapshot maintained by the assigned
contributor.

Partner Metadata is visible in Presenter View as context, but does not feed:

- Word reports
- Executive email drafts
- Executive Summary
- Decision Board

For now, those outputs use Approved Updates only.

### 11.2 Edit Permissions

Only the assigned contributor can edit Partner Metadata.

Metadata changes go live when the contributor clicks Save Metadata.

### 11.3 Monthly Snapshots

Partner Metadata should be stored as monthly snapshots.

Rules:

- Metadata is saved for the currently selected month/cycle.
- If the contributor edits metadata multiple times in the same month, only the latest saved version for that month matters.
- No intra-month version history is required.
- Old monthly snapshots should remain available for history/monthly context.

### 11.4 Required Metadata Fields

Partner Metadata fields:

1. Highlights / Status
2. Business Priority
3. Goals
4. Key Risks & Issues
5. Resource Links

### 11.5 Highlights / Status

Contributor manually provides:

- Overall status
- Free-text highlights/status

No AI assistance is needed for metadata entry.

Overall status scale:

- On Track - Green
- At Risk - Amber
- Blocked - Red

### 11.6 Business Priority

Business Priority is free text only.

Contributor explains business priority in their own words.

### 11.7 Goals

Goals should be a bullet list.

### 11.8 Key Risks & Issues

Key Risks & Issues should be shown in a tabular format.

Columns/fields:

- Item number/index
- Description
- Go-to-green action
- Severity
- Assigned owner
- Due date
- Ramification
- Remove/delete action

## 12. Resource Links

### 12.1 Purpose

Resource Links are convenience/access links on Partner Metadata.

They are not training settings.
They are not ingestion settings.
They can be any useful partner link.

Examples:

- Jira links
- Jira epics or comments
- SharePoint folders or files
- Confluence pages
- GitHub repositories
- Random useful URLs

The app should not assume Resource Links can be used for update extraction.

### 12.2 Resource Link Fields

Each Resource Link has:

- Title
- URL
- Optional description

Resource type is not required for Resource Links.

### 12.3 Resource Link Behavior

Resource Links are partner-level current resources and should be shown at all
times.

Assigned contributor can:

- Add Resource Links
- Edit Resource Links
- Remove Resource Links

If a link was automatically created from a Connected Source:

- Contributor can still edit/remove it like any other Resource Link.
- Removing the Resource Link does not disable or archive the Connected Source.

### 12.4 Connected Source Relationship

Adding a link-based Connected Source should automatically create a Resource Link.

Exception:

- Slack Connected Sources should not automatically create Resource Links.

If a Connected Source is archived/disabled, any related Resource Link can still
exist, but may be shown as disabled/inactive for now.

## 13. Connected Sources

### 13.1 Purpose

Connected Sources are partner-specific sources that can generate Pending Updates
after Admin approval and system testing.

Connected Sources are separate from Resource Links.

Resource Links answer:

- "Where can I quickly access useful partner information?"

Connected Sources answer:

- "Which sources should the system actively use to generate Pending Updates?"

### 13.2 Integration Configuration Layers

There are two configuration layers:

1. System-level integration configuration
2. Partner/contributor-level Connected Source configuration

System-level configuration is owned by Admin.

Examples:

- Slack signing secret
- Slack bot token / app credentials
- Jira webhook secret
- Jira backend/MCP credentials
- SharePoint app credentials
- Confluence integration credentials
- GitHub app/token credentials
- Global enable/test status

Partner-level Connected Source configuration is owned by the assigned contributor
but requires Admin approval.

Examples:

- Slack channel name and channel ID
- Jira issue URL
- SharePoint file URL
- Confluence page URL
- GitHub repo/issue/PR URL

### 13.3 Connected Source Base Fields

Every Connected Source has:

- Name
- Type
- URL or identifier
- Status
- Created by
- Approved by
- Timestamps

Contributor input should be minimal. The system should detect names/titles/types
where possible.

### 13.4 Connected Source Statuses

Contributor-visible statuses:

- Pending
- Active
- Rejected

Admin-visible statuses:

- Pending
- Needs Access Setup
- Active
- Disabled
- Rejected
- Failed

Contributor should not see detailed technical statuses such as Failed or Needs
Access Setup directly. These are Admin/internal statuses.

### 13.5 Connected Source Request Flow

Flow:

1. Contributor submits Connected Source request.
2. Contributor sees status Pending.
3. Admin reviews request.
4. Admin approves or rejects.
5. If Admin rejects, contributor sees Rejected.
6. If Admin approves, system tests access.
7. If test passes, source becomes Active.
8. If test fails, Admin sees Failed/Needs Access Setup internally.

Admin cannot approve a Connected Source if the global integration is not enabled.

If a global integration is disabled:

- Contributor can still submit a Connected Source request.
- Contributor sees Pending.
- Admin queue shows whether the global integration is enabled.
- Admin must configure/test/enable global integration before approval.

### 13.6 Admin Approval

Admin reviews:

- Whether the source type is supported
- Whether access/setup is complete

Admin does not need to deeply validate:

- Partner correctness
- Contributor rule guidance

Admin rejection does not require a reason.

Admin cannot arbitrarily set any status. Admin approves/rejects, while system
tests determine Active/Failed where applicable.

### 13.7 Contributor Management

Contributor can:

- Submit Connected Source requests
- View Pending, Active, and Rejected sources
- Resubmit a rejected source after fixing it
- Pause/resume active sources

Contributor should not delete Connected Sources. Sources should be archived or
disabled to preserve history.

If a Connected Source is archived/disabled:

- Old Approved Updates remain official.
- Existing Pending Updates remain visible/reviewable.

Rejected Pending Updates disappear from the main queue.

### 13.8 Contributor Testing

Contributor should not run source access tests before submission.

Admin/system handles testing during approval.

## 14. Supported Connected Source Types

Connected Sources supported in the product model:

- Jira
- Slack
- SharePoint
- Confluence
- GitHub

## 15. Jira Connected Sources

### 15.1 Source Scope

Jira Connected Source represents a single Jira issue only.

Contributor input:

- Jira issue URL only

System should extract the issue key and generate name/title from Jira.

### 15.2 Event Behavior

Future Jira webhook events for the issue should create Pending Updates only for
meaningful changes.

The developer-owned Jira rulebook governs what should be drafted and what should
be ignored.

The rulebook should be broad enough to reduce risk of losing important
information.

Meaningful Jira event categories include:

- Comments
- Due date / target date changes
- Priority / severity changes
- Description / summary changes
- Status / resolution changes

Assignee/owner changes are not primary meaningful categories for now.

### 15.3 Source Link

Jira Pending Updates should link to the main Jira issue.

No need to deep-link to the exact comment/change for now.

### 15.4 Raw Content Storage

Jira raw issue/event content may be stored fully behind the scenes for technical
processing.

Rules:

- Raw Jira content is not shown directly in the UI.
- It is used only for technical processing, dedupe, audit, AI reprocessing, and
  memory.

## 16. Slack Connected Sources

### 16.1 Source Scope

One Slack channel maps to exactly one partner.

Contributor input:

- Channel name
- Channel ID
- Confirmation checkbox that bot/app has been invited

Slack Connected Sources do not automatically create Resource Links.

### 16.2 Admin Approval Test

Slack approval test should verify:

- Channel exists
- Bot/app has access

If the API can confirm access, the source becomes Active.

### 16.3 Event Behavior

Slack source should process:

- All channel messages
- All thread replies

The system should not create updates for every message.

Draft generation should use:

1. AI/rulebook meaningfulness filtering as the primary method
2. Keywords/topics as supporting signals

### 16.4 Source Link

Slack Pending Updates should link to the Slack channel, not the exact message or
thread.

### 16.5 Raw Content Storage

For Slack:

- Do not store raw message content.
- Store only generated Pending Update text and channel link.
- Store technical metadata only for dedupe/debugging.

Allowed technical metadata:

- Slack event ID
- Channel ID
- Message timestamp
- Thread timestamp
- Sender ID hash or similar non-content identifier

No raw Slack message text should be retained.

## 17. SharePoint Connected Sources

### 17.1 Source Scope

SharePoint Connected Source represents a single file only.

Contributor input:

- SharePoint file URL only

System should detect:

- File name
- File type

### 17.2 Supported File Types

Supported SharePoint file types:

- Word / DOCX
- PowerPoint / PPTX
- Excel / XLSX
- PDF

### 17.3 Event Behavior

When the SharePoint file changes:

- The system should process the updated file.
- The developer-owned SharePoint/document rulebook should govern extraction.
- The rulebook may account for document structure/context.

### 17.4 Storage

The app should store a copy of the SharePoint file itself for processing.

Access to view/download the stored copy from inside the app depends on original
SharePoint permissions.

The app must not become a permission bypass.

## 18. Confluence Connected Sources

### 18.1 Source Scope

Confluence Connected Source represents a single Confluence page only.

Contributor input:

- Confluence page URL only

System should detect the page title.

### 18.2 Event Behavior

When the Confluence page changes:

- The system should process the updated page.
- The Confluence MCP/integration should be used similarly to Jira.
- Meaningful changes should generate Pending Updates according to the developer-owned rulebook.

### 18.3 Raw Content Storage

Confluence raw page content may be stored fully behind the scenes for technical
processing only.

Rules:

- No direct UI display of raw Confluence content.
- Used for processing, audit, reprocessing, search, and memory.

## 19. GitHub Connected Sources

### 19.1 Source Scope

GitHub Connected Source can represent:

- Repository
- Issue
- Pull request

Contributor input:

- GitHub URL only

System should detect whether the URL is a repo, issue, or PR.

### 19.2 Repository Event Behavior

For GitHub repository sources, the system should consider all meaningful repo
events according to developer-owned rulebook.

Candidate events include:

- Issues
- Pull requests
- Releases/tags
- Commits
- Security/advisories

### 19.3 Issue/PR Event Behavior

For GitHub issue or PR sources:

- Track only that specific issue or PR.
- Do not infer broader repo context.
- Do not automatically include linked issues/PRs for now.

### 19.4 Raw Content Storage

GitHub relevant raw event/content may be stored behind the scenes for technical
reasons only.

Rules:

- No direct raw-content UI for now.
- Used for backend processing, dedupe, audit, reprocessing, search, and memory.

## 20. Pending Updates

### 20.1 Purpose

Pending Updates are proposed updates awaiting assigned contributor review.

Pending Updates may come from:

- Connected Sources
- Manual contributor entry

### 20.2 Creation Flow

Source-generated flow:

1. Source event/change occurs.
2. System evaluates event using developer-owned rulebook.
3. Meaningful event becomes Pending Update.
4. Pending Update appears in assigned contributor's Pending Updates queue.

Manual flow:

1. Contributor creates manual update in Pending Updates.
2. It appears as a Pending Update.
3. Contributor can approve it later.

Manual updates are source-less.

### 20.3 Review Permissions

Only the assigned contributor can approve Pending Updates for that partner.

Contributor actions:

- Approve
- Edit
- Reject

Contributor cannot:

- Change source link for source-generated updates
- Edit source-owned system metadata
- Change classification fields, because visible classification fields are not part of v1

### 20.4 Display Requirements

Pending Update should show:

- Update text
- Source link for source-generated updates
- Source type in Contributor View

Contributor does not need source excerpt.
Contributor does not see raw source content in the app.

### 20.5 Source Links

Source-generated Pending Updates have one source link.

Manual updates have no source link.

Source link is system-owned and immutable for source-generated updates.

### 20.6 Sorting And Filtering

Pending Updates default sort:

- Newest first

Pending Updates filters:

- Source type
- Month/cycle

### 20.7 Duplicate Detection

Exact duplicate definition:

- Same source URL
- Same generated update text

Exact duplicates should be rejected/suppressed automatically.

If two Pending Updates have the same source URL but different generated text:

- Keep both.
- Contributor decides.

Near duplicates or slightly changed items should remain as Pending Updates.

### 20.8 Rejection

Contributor can reject Pending Updates.

Rejection:

- Does not require a reason.
- Removes the item from the main queue.
- Does not require rejected history for now.

### 20.9 Editing

Contributor may edit Pending Update text before approval.

Editing:

- Is optional.
- Does not require saving intermediary version history.
- Only latest edited text or final approved text matters.

Pending and Approved Updates are plain text only.

No rich text, Markdown, or source-derived formatting for v1.

## 21. Approved Updates

### 21.1 Purpose

Approved Updates are official contributor-approved updates.

They are the source of truth for:

- Live intelligence
- Monthly Word report
- Executive email draft
- Executive Summary
- Decision Board
- Partner memory/training

### 21.2 Approval

Only assigned contributor can approve.

Manual updates:

- Month/cycle is assigned based on the date contributor approves the draft.

Source-generated updates:

- Month/cycle is assigned based on source event timestamp.
- If source event happened in July but approval happens in August, update belongs to July.

Contributor cannot manually change month/cycle.

### 21.3 Immutability

Approved Updates are immutable once approved.

Contributor cannot:

- Edit Approved Update
- Delete Approved Update
- Withdraw Approved Update

If an Approved Update is wrong:

- Contributor creates a new manual Pending Update as a correction.
- No special correction type is required for v1.

### 21.4 Data Shape

Approved Update has:

- Text
- Partner
- Month/cycle
- Source link if source-generated
- No source link if manual

No visible classification fields for v1.

Do not show:

- Signal type
- Report category
- AI tags
- Workstream/topic tags

### 21.5 Display

Contributor Approved Updates:

- Newest first flat list
- Filter by source type
- Filter by month/cycle
- Source type visible in Contributor View

Presenter Approved Updates:

- Filter by partner
- Filter by month/cycle
- Source type hidden

### 21.6 Approved Updates From Disabled Sources

If a Connected Source is archived/disabled:

- Old Approved Updates remain official.
- Old Approved Updates continue to exist in intelligence/reporting history.

## 22. Month And Cycle Rules

No monthly close/freeze process for now.

Past months can receive late-approved source updates if the source timestamp
belongs to that month.

Rules:

- Source-generated update month = source event timestamp month.
- Manual update month = approval date month.
- Contributor cannot manually change month/cycle.

## 23. Presenter View

### 23.1 Purpose

Presenter View provides global read-only visibility across all partners.

Presenter View should show:

- Partner Metadata as-is
- Approved Updates as-is
- Separate analysis sections

Analysis should not replace the underlying data.

### 23.2 Access

Presenter access is Admin-controlled.

Presenter View:

- Shows all partners globally.
- Is read-only for source data and metadata.

### 23.3 Default Filters

Default partner selection:

- All partners selected

Default month/cycle:

- Current calendar month

Presenter Approved Updates filters:

- Partner
- Month/cycle

### 23.4 Presenter Actions

Presenter can:

- View Partner Metadata
- View Approved Updates
- View Executive Summary
- View Decision Board
- Generate Word monthly report
- Generate executive email draft
- Download generated artifacts

Presenter cannot:

- Edit Partner Metadata
- Approve Pending Updates
- Edit Approved Updates
- Edit reports
- Curate report output for now

## 24. Presenter Analysis

Presenter analysis should be separate from metadata and approved update lists.

Analysis sections:

1. Executive Summary
2. Decision Board

Both use Approved Updates only.

Partner Metadata does not feed analysis for v1.
Pending Updates do not feed analysis.
Raw source content does not feed visible analysis directly except through
Approved Updates.

### 24.1 Executive Summary

Executive Summary scope:

- Selected subset of partners

Default selected subset:

- All partners selected by default in Presenter View

Source data:

- Approved Updates only

Format/length:

- Same as current app behavior for now.

Load behavior:

- Auto-load on page load.
- Regenerate every page load.

### 24.2 Decision Board

Decision Board scope:

- Selected subset of partners

Default selected subset:

- All partners selected by default in Presenter View

Source data:

- Approved Updates only

Decision Board should show:

- Risks and blockers
- Asks / decisions needed
- Upcoming deadlines

Decision Board UI:

- Same as current app behavior for now.

Load behavior:

- Auto-load on page load.
- Regenerate every page load.

## 25. Reports And Generated Outputs

### 25.1 Supported Outputs For V1

Presenter can generate:

- Word monthly report
- Executive email draft

PowerPoint generation is not required for now.

### 25.2 Word Monthly Report

Availability:

- Presenter only

Scope:

- All Approved Updates for selected month across all partners

Content:

- Approved Updates only
- No Partner Metadata

Format:

- Structured document/list

### 25.3 Executive Email Draft

Availability:

- Presenter only

Scope:

- All Approved Updates for selected month across all partners

Content:

- Approved Updates only
- No Partner Metadata

Format:

- AI-written summary
- Follows developer-owned executive email rulebook / skills-style file

### 25.4 Word vs Email Relationship

Both use the same Approved Updates input.

Difference:

- Word report is structured/list-oriented.
- Executive email is AI-written summary.

### 25.5 Artifact Storage

Generated Word report and executive email draft:

- Saved as latest artifact per month.
- Overwritten on regeneration.
- Downloadable.

### 25.6 Auto-Regeneration

If Approved Updates change after report/email generation:

- Word report and executive email should auto-regenerate.
- Auto-regeneration should happen immediately when an update is approved.

If regeneration fails:

- Approval should still succeed.
- System should retry silently.
- After several failures, an Admin alert can be shown later.
- Admin Alerts/Issues area is later, not required in first pass.

## 26. Admin View

### 26.1 Purpose

Admin View is the control plane for:

- Users
- Roles/capabilities
- Partners
- Contributor assignments
- Global integration setup
- Connected Source approvals

Admin View does not manage rulebooks for v1.

### 26.2 User Management

Admin can:

- Create users
- Enter name and email
- Assign contributor capability
- Assign presenter capability
- Assign partner ownership
- Deactivate/reactivate users

User invitations:

- Desired eventually.
- Do not implement invite emails for first pass.

Pre-SSO access:

- Users log in with email and shared default password.

SSO later:

- Replaces password login.

### 26.3 Partner Management

Admin can:

- Create partner
- Edit basic partner identity
- Assign contributor owner
- Archive partner

Each partner must have exactly one contributor owner for Contributor View.

### 26.4 Global Integration Setup

Admin can configure:

- Jira
- Slack
- SharePoint
- Confluence
- GitHub

Each integration setup page should include:

- Credentials/config
- Enable/test status
- Connection test
- Setup instructions

Credentials/secrets:

- Entered in Admin UI.
- Not visible after saving.
- Admin can replace/rotate credentials.

Global integration enablement:

- Integration becomes enabled when connection test passes.

If integration later fails:

- Admin decides whether to disable it.

### 26.5 Connected Source Approval Queue

Admin queue should show:

- All Connected Source statuses
- Whether global integration is enabled
- Detailed technical errors/status for source setup/testing

Admin can:

- Approve request
- Reject request

Admin cannot:

- Approve if global integration is not enabled
- Arbitrarily change any status manually

When Admin approves:

- System immediately tests access.
- Source becomes Active only if test passes.

If test fails:

- Admin sees Failed/Needs Access Setup internally.
- Contributor should not see detailed technical error.

## 27. Rulebooks

Rulebooks are developer-owned only for now.

Developer-owned rulebooks include:

- Global/source extraction rules
- Jira extraction rules
- Slack extraction rules
- SharePoint/document extraction rules
- Confluence extraction rules
- GitHub extraction rules
- Executive email writing rules

Admin has no rulebook controls.

Contributor has no free-text processing guidance for Connected Sources.

When contributor adds a Connected Source:

- They provide only structured fields/settings.
- No optional guidance text box.

## 28. Source Content And Privacy Rules

### 28.1 General

Users should not directly see raw source content inside the app unless explicitly
allowed by source-specific rules.

Contributor review UI should show:

- Pending Update text
- Source link

No source excerpt needed.

Original source access:

- User can open source link in external tool if they have permission there.
- The app should not bypass external source permissions.

### 28.2 Source-Specific Storage Rules

Jira:

- Store full raw issue/event content behind the scenes.
- Do not show raw content in UI.

Slack:

- Do not store raw message content.
- Store technical metadata only.

SharePoint:

- Store copy of file.
- In-app access to stored copy depends on original SharePoint permissions.

Confluence:

- Store full raw page content behind the scenes.
- Do not show raw content in UI.

GitHub:

- Store full relevant raw event/content behind the scenes.
- Do not show raw content in UI for now.

## 29. Non-Goals For First Pass

These are intentionally out of scope for the first product-shaped pass:

- Full frontend/backend rewrite
- Presenter report editing/curation
- PowerPoint generation
- Admin-managed rulebook editing
- Contributor source-specific AI guidance
- Partner-level contributor rulebook
- User invitation emails
- OTP/magic-link login
- SSO implementation
- Visible raw source content UI
- Rich text updates
- Update edit history
- Approved Update deletion/editing
- Rejected update history
- Monthly close/freeze
- Polling as a core product concept
- Admin Alerts/Issues UI

## 30. Open Questions

The following are not fully finalized and may need future discussion:

1. Admin role assignment
   - Earlier decision: Admin role should be bootstrap/config protected.
   - Later discussion mentioned Admin creating users and assigning roles broadly.
   - Recommended v1: keep Admin capability protected via bootstrap/config.

2. Exact current UI preservation
   - Some areas should remain "same as now":
     - Manual update creation behavior
     - Executive Summary format
     - Decision Board UI
   - These should be validated against the current UI during implementation.

3. Report/email templates
   - Inputs and permissions are clear.
   - Exact document formatting can follow current behavior unless changed later.

4. Admin alert behavior
   - Silent retries are desired.
   - Admin alerts after repeated failures are desired later.
   - First pass does not require an Alerts/Issues UI.

5. Global integration secret fields
   - Integrations are identified.
   - Exact credential fields per integration need implementation-specific definition.

## 31. First-Pass MVP Scope

The first product-shaped pass should focus on:

1. Contributor View
   - Partner selector
   - Pending Updates
   - Partner Metadata
   - Approved Updates
   - Connected Sources

2. Pending/Approved Update lifecycle
   - Source/manual Pending Updates
   - Contributor approve/edit/reject
   - Approved Update immutability
   - Month/cycle rules

3. Partner Metadata
   - Monthly snapshot fields
   - Resource Links

4. Connected Sources
   - Contributor request flow
   - Admin approval flow
   - Active/Pending/Rejected contributor visibility

5. Admin View
   - Users
   - Partners
   - Integration setup
   - Connected Source approvals

6. Presenter View
   - All partners read-only
   - Approved Updates
   - Partner Metadata
   - Executive Summary
   - Decision Board

7. Reports
   - Word monthly report
   - Executive email draft
   - Latest per month downloadable artifact
   - Auto-regenerate after update approval

## 32. Acceptance Criteria Summary

### Contributor

- Contributor can select from assigned partners.
- Contributor defaults to Pending Updates after selecting a partner.
- Contributor can approve/edit/reject Pending Updates.
- Contributor can manually create Pending Updates.
- Contributor can edit Partner Metadata for assigned partners.
- Contributor can add/edit/remove Resource Links.
- Contributor can submit Connected Source requests.
- Contributor can see Pending, Active, and Rejected Connected Sources.
- Contributor can pause/resume Active Connected Sources.
- Contributor cannot edit/delete Approved Updates.
- Contributor cannot approve updates for unassigned partners.

### Presenter

- Presenter can access Presenter View.
- Presenter sees all partners by default.
- Presenter default month is current calendar month.
- Presenter can filter by partner and month/cycle.
- Presenter can view Partner Metadata.
- Presenter can view Approved Updates.
- Presenter can view auto-loaded Executive Summary.
- Presenter can view auto-loaded Decision Board.
- Presenter can generate/download Word monthly report.
- Presenter can generate/download executive email draft.
- Presenter cannot edit reports for now.

### Admin

- Admin can create users with name/email.
- Admin can assign contributor/presenter capabilities.
- Admin can assign contributors to partners.
- Admin can create/edit/archive partners.
- Admin can configure and test global integrations.
- Admin can save/replace secrets without viewing saved values.
- Admin can review Connected Source requests.
- Admin can approve/reject Connected Sources.
- Admin sees detailed technical errors/status.
- Admin cannot approve source if global integration is disabled.

### System

- Source-generated updates become Pending Updates only when meaningful.
- Exact duplicates are suppressed.
- Same source URL with different generated text creates separate Pending Updates.
- Approved Updates are immutable.
- Source-generated update month comes from source event timestamp.
- Manual update month comes from approval date.
- Approved Updates feed reporting, analysis, and memory.
- Word/email artifacts are latest per month and downloadable.
- Word/email artifacts auto-regenerate immediately after approval.

