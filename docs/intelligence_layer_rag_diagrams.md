# Intelligence Layer And RAG Flow

This project's intelligence layer is a review-gated RAG system. Uploaded files
are parsed into candidate facts, profiled, reviewed by a human, and only then
enabled for retrieval by dashboards, smart analysis, and the presenter
assistant.

## 1. Simple Intelligence Layer Diagram

```mermaid
flowchart LR
    A["Knowledge Upload<br/>DOCX / PPTX / XLSX"] --> B["Parsers<br/>doc_parser / ppt_parser / xlsx_parser"]
    B --> C["Candidate Extraction<br/>knowledge_upload_candidates"]
    C --> D["Profiling Layer<br/>partner, cycle, entity, quality, tags"]
    D --> E{"Human Review"}
    E -->|Approve| F["Approved Knowledge<br/>updates + historical_updates"]
    E -->|Dismiss / Duplicate| G["Non-retrievable archive"]
    E -->|Needs mapping| H["Partner / Topic / Event Mapping"]
    H --> D
    F --> I["Retrievable Chunks<br/>document_chunks.retrieval_enabled = true"]
    F --> J["Partner Memory<br/>partner_memory + workstream_context"]
    I --> K["RAG Retrieval<br/>search_source_documents"]
    J --> K
    K --> L["Presenter Assistant<br/>grounded answer + citations"]
    F --> M["Dashboards / Smart Analysis / PPT / Email"]
```

## 2. How RAG Works In This Project

```mermaid
sequenceDiagram
    participant Admin as Admin Upload
    participant Parser as File Parsers
    participant Profiler as Profiling Rules
    participant Review as Human Review UI
    participant Store as Intelligence Store
    participant Retrieve as Retrieval Layer
    participant Assistant as Presenter Assistant

    Admin->>Parser: Upload DOCX, PPTX, or XLSX
    Parser->>Profiler: Extract records, links, outline path, structured data
    Profiler->>Review: Create candidates with confidence and review status
    Review->>Store: Commit selected approved candidates
    Store->>Store: Insert approved update and historical update
    Store->>Store: Enable document chunk retrieval
    Store->>Store: Refresh partner memory and workstream context
    Assistant->>Retrieve: Ask question with partner, cycle, workstream scope
    Retrieve->>Store: Search approved updates, historical training, source chunks, memory
    Store-->>Assistant: Return approved evidence with citation IDs
    Assistant-->>Admin: Answer only from retrieved evidence
```

## 3. Profiling Parameters

| Parameter | Meaning | Where It Is Used |
| --- | --- | --- |
| `partner_slot` | Configured partner identity such as Google, Microsoft, AWS, etc. | Access control, dashboards, update grouping, retrieval scope |
| `partner` | Human-readable partner name | Presenter views and generated content |
| `cycle` | Reporting period such as `Jul-2026` | Monthly/quarterly filtering and retrieval |
| `entity_type` | `partner`, `topic`, or `event` | Decides whether an item becomes software ecosystem intelligence or topic/event knowledge |
| `entity_key` | Stable key for the partner/topic/event | Mapping, dedupe, and entity memory |
| `section_label` | Source section/workstream label | Workstream grouping and context |
| `quality_score` | Heuristic score from 0 to 1 based on whether the text is actionable | Review triage |
| `partner_confidence` | Confidence that the candidate belongs to the identified partner | Review triage |
| `update_confidence` | Confidence that the text is a useful business update | Review triage and approved update confidence |
| `review_status` | `ready`, `needs_mapping`, `likely_noise`, `duplicate`, `approved`, or `dismissed` | Controls whether an item can be committed |
| `retrieval_enabled` | Boolean gate for whether a chunk can be retrieved by RAG | Prevents unapproved data from reaching the assistant |
| `embedding` | Stored vector representation of the text or memory summary | Prepared for semantic/vector retrieval |
| `links_json` | Source evidence links | Citations and provenance |
| `linked_evidence_json` | Parsed evidence from linked docs/pages | Richer source provenance |
| `structured_data_json` | Parser-specific structured facts from decks/trackers | Smart analysis and presenter summaries |
| `presenter_summary` | Human-approved presenter-friendly wording | Dashboard, assistant, email, and PPT outputs |

## 4. Retrieval Sources Used By The Presenter Assistant

```mermaid
flowchart TB
    Q["Presenter Question"] --> S["Scope Resolver<br/>partner + cycle + workstream"]
    S --> A["Approved Updates<br/>updates"]
    S --> H["Historical Training<br/>historical_updates"]
    S --> D["Approved Source Chunks<br/>document_chunks"]
    S --> P["Partner Memory<br/>partner_memory"]
    S --> W["Workstream Memory<br/>workstream_context"]
    S --> C["Admin Metadata<br/>partners, owners, workstreams, instructions"]
    A --> R["Context Payload"]
    H --> R
    D --> R
    P --> R
    W --> R
    C --> R
    R --> O["OpenAI Response<br/>JSON answer, citations, follow-ups"]
```

The assistant is intentionally constrained: it must answer from supplied tool
data only, and it must not expose staged, dismissed, duplicate, or unapproved
records.

## 5. Current Versus Future Retrieval

```mermaid
flowchart LR
    A["Current Local Retrieval"] --> B["SQLite keyword search<br/>approved chunks only"]
    B --> C["Rank by term overlap<br/>limit scoped results"]
    C --> D["Assistant synthesis with citations"]

    E["Future Production Retrieval"] --> F["Postgres + pgvector"]
    F --> G["Embedding similarity + metadata filters"]
    G --> D
```

Current implementation stores embeddings during upload/commit, but the local
retrieval path is SQLite-friendly keyword search over approved chunks. The
natural production upgrade is Postgres with `pgvector`, keeping the same
approval and metadata gates.

## 6. Suggested Presentation Narrative

1. We do not treat uploaded decks and trackers as trusted knowledge immediately.
2. The system parses each file into candidate facts with partner, cycle, entity,
   confidence, quality, links, and structured evidence.
3. A human review step decides what becomes approved intelligence.
4. Only approved intelligence becomes retrievable in the RAG layer.
5. The assistant and Smart Analysis use this curated layer to answer questions,
   produce cited summaries, and generate presenter-ready material.

