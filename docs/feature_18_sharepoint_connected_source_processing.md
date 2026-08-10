# Feature 18 - SharePoint Connected Source Processing

Feature 18 adds SharePoint single-file connected source processing for Cloud AI
Software Ecosystem Updates.

## Scope

- SharePoint webhook endpoint:
  - `POST /api/webhooks/sharepoint/events`
- Microsoft Graph validation-token response support.
- Notification `clientState` validation using admin-configured SharePoint
  Client State.
- Active connected-source mapping by SharePoint file URL/web URL.
- Source event enqueueing for approved SharePoint file sources.
- Duplicate protection using a hashed SharePoint event identity.
- Local file-copy storage foundation through `storage_objects`.
- Source payload linkage to stored file copies.
- Immediate local processing into Pending Updates when extracted file text passes
  the developer-owned SharePoint/document meaningfulness rule.

## Credential Boundary

Global SharePoint / Microsoft Graph credentials remain admin-owned:

- Tenant ID
- Client ID
- Client Secret
- Client State

Contributor-owned configuration remains source-specific:

- partner
- single SharePoint file URL

Folder, library, site, and broad-drive ingestion remain out of scope for v1.

## Storage Behavior

SharePoint file processing stores a copy of the downloaded file for processing.
In local development this uses the configured local upload storage directory.
In AWS this should move to S3 using the same `storage_objects` contract.

The source event stores technical metadata only. Raw Graph notification payloads
are not persisted in `source_payloads`.

`source_payloads.storage_object_id` links the source event to the stored file
copy when content is available.

## Processing Rule

The current local rulebook is deterministic and developer-owned:

- process only active single-file SharePoint connected sources
- ignore unmapped or ambiguous notifications
- require a valid notification `clientState`
- use extracted text from the stored file copy
- create a Pending Update when the extracted text is long enough or includes a
  business-relevant keyword such as risk, blocker, decision, milestone, status,
  release, priority, issue, or update

This is a placeholder extraction layer. Later agentic extraction can use a
document-specific rulebook and richer parsers for DOCX, PPTX, XLSX, and PDF.

## Not In Scope

- Folder-wide SharePoint ingestion.
- Site/library-wide SharePoint ingestion.
- Live Microsoft Graph subscription creation.
- Live Microsoft Graph file download validation.
- Full DOCX/PPTX/XLSX/PDF semantic parsing.
- Storing Graph notification raw payloads.
- Bypassing original SharePoint permissions for in-app file access.
