# ADR-003: Qdrant for Vector Storage

**Status:** Accepted  
**Date:** 2026-10-13

## Context

RAG requires embeddings at pilot scale with metadata filtering per library/project.

## Decision

Use **Qdrant** (single instance, NFS-backed persistence) with:

- Embedding model **BAAI/bge-m3**
- Reranker **BAAI/bge-reranker-v2-m3**

Chunk payloads store citation fields; full text may remain on NFS.

## Consequences

- Operational component to deploy beside Postgres on CAI
- **M2 default design:** shared collection + payload filters — **not finalized** until validation gate (latency, recall, filter overhead, isolation, volume) — see [RAG_DESIGN.md](../backend/RAG_DESIGN.md)

## Alternatives considered

- pgvector — simpler stack but weaker pilot ergonomics for hybrid search at scale
- OpenSearch — heavier ops for accelerator default
