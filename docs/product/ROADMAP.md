# Cloudera AI Accelerator — Roadmap

## Milestones

### M0 — Architecture & contracts ✅

- Codebase audit (`frontend-dev`, `backend-dev`)
- Target architecture, data model, API/SSE contracts
- ADRs, `PROJECT_STATE.md`

### M1 — Platform foundation ✅

- Store abstraction (`ConversationStore` / `UsageStore`, sqlite + postgres)
- Workspace / project API + OSSIE path resolution
- PostgreSQL metadata (Alembic `m1_platform_001`) + default seed
- SecretProvider (`EnvSecretProvider`)
- FE capability flags + branding config
- Preserve `/chat`, `/chat/stream`, `AskDataResponse`

See [M1_PLATFORM_FOUNDATION.md](../architecture/M1_PLATFORM_FOUNDATION.md).

### M2 — Document Intelligence / RAG (next)

- Document registry + NFS layout
- Parser interface (Docling adapter)
- Chunk → embed (bge-m3) → Qdrant
- Ingestion worker (simple queue or background tasks)
- RAG query path + **mandatory citations**
- FE: Documents / Libraries (minimal)

### M3 — Prompt management + Skills

- Prompt + PromptVersion entities, activation/rollback
- Prompt assembly hierarchy (global → project → skill → session)
- Skill + SkillVersion manifests (tools, permissions, output contract)
- FE: Prompts + Skills pages (replace Studio placeholders when product merges)

### M4 — Connectors

- Connector adapter interface
- Impala + Trino structured connectors (refactor from current `db/` backends)
- Connector test/sync metadata jobs
- Future: Slack/Gmail → sync → document pipeline (design only in M4 docs)

### M5 — Hybrid routing

- Intent / skill router (`ask_data` | `rag` | `hybrid` | `general` | `clarification`)
- Hybrid analyzer combining structured results + citations
- Unified response contract consumed by FE without engine-specific branches

### M6 — Accelerator packaging

- CAI application templates, env documentation
- Sample OSSIE project slot (customer replaces `projects/<id>/`)
- Operator runbooks, seed scripts, health checks

## Dependencies

```text
M0 → M1 → M2 ──┐
         M3 ────┼→ M5 → M6
         M4 ────┘
```

M2 and M3 can overlap after M1; M5 requires RAG + stable Ask Data.

## Risks (summary)

See [MIGRATION_PLAN.md](./MIGRATION_PLAN.md).
