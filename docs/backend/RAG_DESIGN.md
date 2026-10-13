# RAG / Document Intelligence — Design

**Status:** M2 target — not implemented in `backend-dev`.

## Ingestion pipeline

```text
Upload (HTTP multipart)
  → Document Registry (Postgres: status=uploaded, nfs_uri)
  → Parser (Docling preferred; Parser interface)
  → Normalizer (text + structure)
  → Chunker (size/overlap policy per library)
  → Embedder (BAAI/bge-m3)
  → Qdrant upsert (vector + payload)
  → status=ready
```

Failures set `status=failed` with error on document row; retry via job.

## NFS layout (pilot)

```text
${NFS_ROOT}/
  workspaces/{workspace_id}/
    projects/{project_id}/
      documents/{document_id}/original.{ext}
      parsed/{document_id}/docling.json
      attachments/
      exports/
```

Postgres stores **pointers only**.

## Parser interface

```python
class DocumentParser(Protocol):
    def parse(self, source_path: Path, mime_type: str) -> ParsedDocument: ...
```

`ParsedDocument`: pages[], blocks[], tables optional, language.

Implementations: `DoclingParser` (default), future `PlainTextParser`, `PdfMinerFallback`.

## Chunk model

- Config per library: `chunk_size_tokens`, `overlap`, `split_by` (page | heading)
- Store chunk text snippet in Qdrant payload (size cap) + full text optional on NFS

## Query flow

```text
Question
  → route=rag
  → Query rewrite (optional LLM)
  → Metadata filters (library_id, project_id, doc types)
  → Vector search (Qdrant top-k)
  → Rerank (bge-reranker-v2-m3)
  → Context builder (token budget)
  → LLM answer
  → Citations[] (mandatory)
```

## Citation representation

Each citation in unified response:

```json
{
  "document_id": "uuid",
  "filename": "policy-q4.pdf",
  "page": 12,
  "section": "Promo Policy",
  "chunk_id": "uuid",
  "source_uri": "nfs://...",
  "snippet": "…",
  "score": 0.87
}
```

UI: inline markers `[1]` mapping to citation list; workspace “Sources” tab (future).

## Qdrant payload (minimum)

- `workspace_id`, `project_id`, `library_id`, `document_id`, `chunk_id`
- `page`, `section`, `filename`
- `text_snippet`

## Qdrant collection strategy

**Default M2 design (not finalized):** **shared collection + mandatory metadata filtering** on every query:

- Payload fields: `workspace_id`, `project_id`, `library_id`, `document_id`, `chunk_id`, …
- Typical starting point: **one shared collection per pilot environment** (or per default workspace), not one collection per library.

**Do not finalize** collection topology until the **M2 validation gate** completes.

### M2 validation gate (required before locking strategy)

Evaluate against expected pilot **chunk and document volume**:

| Criterion | What to measure |
|-----------|-----------------|
| **Retrieval latency** | p50/p95 vector search + rerank under load |
| **Recall quality** | golden-set hit rate @ k vs baseline |
| **Metadata filtering overhead** | filter-only vs unfiltered latency delta |
| **Isolation correctness** | no cross-library / cross-project leakage in filtered queries |
| **Volume scaling** | index size, upsert throughput, delete/reindex time |

**If shared collection fails pilot requirements:** revisit **collection-per-library** or **collection-per-workspace** (document decision in ADR-003 addendum or new ADR).

| Approach | Status |
|----------|--------|
| **Shared collection + filters** | **Default M2 implementation path** |
| **Per-library / per-workspace collections** | **Fallback** after failed gate |

**`library.qdrant_collection`:** **null** in shared mode; populated only if fallback mode is adopted.

## M2 worker architecture (accelerator mode)

| Mode | Use |
|------|-----|
| **Default** | FastAPI **BackgroundTasks** — parse, chunk, embed, reindex triggered from upload API |
| **Optional** | **RQ** + Redis when CAI provides Redis or jobs need durability, retries, or run > ~2 min |

Job status tracked in Postgres (`document.status`, optional `connector_sync_job`). See [ADR-005](../decisions/ADR-005-BACKGROUND-JOBS.md).

## API (target)

- `POST /api/v1/libraries/{id}/documents` — upload
- `GET /api/v1/documents/{id}` — status + metadata
- `POST /api/v1/documents/{id}/reindex`
- RAG queries go through unified `/chat` with `route=rag` in response (not separate public RAG endpoint required if hybrid router handles it)

Jobs: parse, chunk, embed, reindex, library delete cascade.

## FE (target)

- Libraries list, upload dropzone (similar UX to CAI Studio Document AI — **new pages in frontend-dev**, not present today)
- Citation panel in chat + Analysis Workspace “Sources”

## Testing strategy (M2)

- Fixture PDFs, mock parser, in-memory Qdrant or test container
- Golden questions with expected citation doc ids
