# Feature 11 - File And Knowledge Upload

## Goal

Preserve file and knowledge upload capability in Cloud AI Software Ecosystem
Updates without prematurely coupling uploads to AI extraction, Connected
Sources, or training workflows.

This feature gives the product a clean upload foundation:

- uploaded file metadata is stored in PostgreSQL
- uploaded bytes are stored through a storage abstraction
- local development uses a Docker volume
- production configuration is ready to point at S3
- contributor uploads are partner-scoped
- admin uploads can be global or partner-scoped

## Product Decisions

- Uploads do not automatically create draft updates in this feature.
- Uploads do not become Connected Sources yet.
- Uploads do not expose raw source excerpts as normal contributor evidence.
- Simple text-like files get a short preview for operator confidence.
- Office/PDF files are stored as durable upload records for later parser/agent work.
- Contributor uploads are only allowed for partners assigned to that contributor.
- Admin Knowledge Upload is a dedicated Admin Console section.
- Contributor file upload is placed inside the existing Connected Sources tab as
  Partner Files to avoid adding a fifth contributor tab.

## Database Scope

Added migration:

- `0006_knowledge_uploads`

Added table:

- `knowledge_uploads`

### `knowledge_uploads`

Key columns:

- `upload_id`
  - Primary key.
- `partner_id`
  - Optional foreign key to `partners.partner_id`.
  - `null` means global admin knowledge.
- `scope`
  - `admin_knowledge` or `contributor_partner_file`.
- `title`
  - User-entered title or filename fallback.
- `description`
  - Optional business context.
- `original_filename`
  - Sanitized filename supplied by the browser.
- `content_type`
  - Browser-provided MIME type.
- `file_size_bytes`
  - Stored byte size.
- `checksum_sha256`
  - File checksum for traceability and later duplicate handling.
- `storage_backend`
  - `local` in this build.
- `storage_key`
  - Internal object key/path, not exposed in the client response.
- `processing_status`
  - `parsed` for simple text-preview files.
  - `stored` for files stored without text preview.
- `text_preview`
  - Short preview for supported text files.
- `uploaded_by`
  - Foreign key to `users.user_id`.

Indexes:

- `partner_id`
- `scope`
- `uploaded_by`
- `partner_id + scope + created_at`

## Backend Scope

Added model:

- `apps/api/app/db/models/knowledge_upload.py`

Added shared upload domain:

- `apps/api/app/domains/uploads/storage.py`
- `apps/api/app/domains/uploads/schemas.py`
- `apps/api/app/domains/uploads/service.py`

Added Admin route:

- `apps/api/app/domains/admin/knowledge_uploads/router.py`

Added Contributor route:

- `apps/api/app/domains/contributor/uploads/router.py`

Updated:

- `apps/api/app/main.py`
- `apps/api/app/core/config.py`
- `apps/api/pyproject.toml`
- `apps/api/uv.lock`

Storage behavior:

- Supported extensions:
  - `.txt`
  - `.md`
  - `.csv`
  - `.json`
  - `.log`
  - `.pdf`
  - `.doc`
  - `.docx`
  - `.ppt`
  - `.pptx`
  - `.xls`
  - `.xlsx`
- Unsupported extensions are rejected.
- Empty files are rejected.
- Files over `MAX_UPLOAD_SIZE_MB` are rejected.
- Local Docker storage uses `/app/var/uploads` with a named Docker volume.

## API Scope

Added:

- `GET /api/admin/knowledge-uploads`
  - Lists all uploads visible to Admin.

- `POST /api/admin/knowledge-uploads`
  - Multipart upload.
  - Fields:
    - `file`
    - `title`
    - `description`
    - `partner_id`
  - Requires Admin role.

- `GET /api/contributor/partners/{partner_id}/uploads`
  - Lists contributor partner-file uploads for an assigned partner.
  - Requires Contributor role.

- `POST /api/contributor/partners/{partner_id}/uploads`
  - Multipart upload.
  - Fields:
    - `file`
    - `title`
    - `description`
  - Requires Contributor role.
  - Requires assigned active partner.

## Client Scope

Added:

- `apps/web/src/features/uploads/uploads-api.ts`
- `apps/web/src/features/uploads/KnowledgeUploadTable.tsx`
- `apps/web/src/features/admin/AdminKnowledgeUploadPanel.tsx`
- `apps/web/src/features/contributor/ContributorUploadsPanel.tsx`

Updated:

- `apps/web/src/features/shell/AccountViewShell.tsx`
- `apps/web/src/features/contributor/ContributorDashboardShell.tsx`
- `apps/web/src/app/globals.css`

Client behavior:

- Admin Console now includes Knowledge Upload.
- Admin can upload global knowledge or associate a file to an active partner.
- Contributor Connected Sources tab now shows Partner Files upload.
- Upload tables show:
  - title
  - original filename
  - partner where relevant
  - content type
  - file size
  - processing status
  - created date
  - short text preview when available

## Acceptance Criteria

- Admin can upload a supported file.
- Admin can list uploaded files.
- Contributor can upload a supported file for an assigned partner.
- Contributor can list uploaded files for an assigned partner.
- Contributor cannot upload files for an unassigned partner.
- Upload records include checksum, size, filename, storage backend, and uploader.
- Text-like files get a short preview.
- Unsupported file extensions are rejected.
- Empty files are rejected.

## Verification Notes

Verified:

- `uv lock` added `python-multipart`.
- Alembic upgraded to `0006_knowledge_uploads`.
- Backend tests passed: 14 tests.
- Ruff check passed.
- Web typecheck passed.
- Web production build passed.
- Docker Compose API and web images rebuilt successfully.
- Docker Compose API service reports healthy.
- API smoke test:
  - logged in as Admin
  - created a temporary partner assigned to Bhumik Patel
  - uploaded admin knowledge file
  - uploaded contributor partner file
  - verified both parsed text previews
  - verified contributor partner upload list
  - verified admin upload list
  - cleaned temporary DB records

## Feature 24 Extension - Guided Admin Knowledge Extraction

Added a Gold-inspired admin review workflow on top of the upload foundation:

- Admin Knowledge Upload now uses a three-step flow:
  - Upload
  - Confirm
  - Results
- Admin uploads are parsed into review candidates before anything reaches
  contributor pending updates.
- Text, CSV, JSON, Markdown, log, DOCX, PPTX, and XLSX files are handled by a
  deterministic parser layer.
- Candidate extraction preserves source evidence, section/slide/row labels,
  detected links, partner mapping, and cycle month.
- Candidates without partner or cycle mapping remain blocked from staging until
  the admin resolves the missing mapping.
- Admins can edit candidate text, map partner/month, dismiss candidates, and
  stage selected candidates.
- Staged candidates become normal pending `partner_updates` with `source_type`
  set to `file` and a durable `knowledge-upload:{candidate_id}` source key.
- The rulebook `admin_knowledge_upload` defines the extraction constraints:
  grounded facts only, preserve quantitative info and links, no semicolon-based
  merging, and no repeated prior-month context.

Added migration:

- `0015_knowledge_upload_candidates`

Added backend pieces:

- `knowledge_upload_candidates`
- `apps/api/app/domains/uploads/analyzer.py`
- admin detail, candidate update/dismiss, and staging routes

Added client behavior:

- Gold-inspired wizard visual treatment
- candidate review cards
- source evidence disclosure
- staged results view

Additional verification:

- Focused Ruff checks passed for touched backend files.
- Python compile check passed.
- Web TypeScript check passed.
- Web production build passed.
- Backend service test covers candidate extraction and staging.
- Docker local API/web rebuilt and running on `localhost:3000`.
- Alembic upgraded local Docker database through
  `0015_knowledge_upload_candidates`.
- Browser smoke test uploaded a temporary SAP HANA Cloud text file, extracted
  two candidates, staged two pending updates, then cleaned the synthetic data.
- Browser UI smoke test:
  - logged in as Bhumik Patel
  - selected a temporary assigned partner
  - opened Connected Sources
  - verified Partner Files upload UI appears
  - seeded a partner file through the authenticated API
  - remounted Connected Sources
  - verified the uploaded file renders in the UI table
  - cleaned temporary DB records

Known local note:

- Browser automation could not control the native file picker in this tool
  surface, so the final browser check verified upload-table rendering after an
  authenticated API seed. API upload behavior itself was smoke-tested directly.
