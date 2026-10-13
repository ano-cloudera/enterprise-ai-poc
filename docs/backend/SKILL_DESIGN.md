# Skills Architecture — Design

## Concept

A **skill** is reusable configuration binding:

- description (for router + UI)
- prompt fragment (via prompt hierarchy)
- allowed tools
- permissions
- expected output behavior

## Example manifest (YAML/JSON in `skill_version.manifest_json`)

```yaml
name: sales_analysis
description: Analyze governed sales metrics for the active project

prompt_ref: prompts/sales-analysis  # or embedded prompt_version_id

tools:
  - semantic_lookup
  - database_query

permissions:
  sql_read_only: true
  max_rows: 500
  allowed_schemas: [gold]

output:
  require_answer: true
  allow_visualization: true
  require_citations: false
  clarification_allowed: true
```

## Storage

- `skill` + `skill_version` tables (see DATA_MODEL.md)
- Versioning same as prompts: create, activate, rollback

## Runtime resolution

1. Intent router selects `skill_id` (explicit user pick, auto classification, or default)
2. Load active `skill_version`
3. Merge permissions into SQL validator + tool registry
4. Attach skill prompt layer in `assemble_prompt()`

## Tool binding

| Tool id | Maps to (today) |
|---------|-----------------|
| `semantic_lookup` | `SemanticContextService.resolve/compile` |
| `database_query` | Connector.fetch after validation |
| `vector_search` | Qdrant retrieval (M2) |
| `document_fetch` | Load NFS parsed doc metadata |

Tools registered in `app/tools/registry.py` (new module M3) — not separate microservices.

## Router integration (M5)

Skills influence route:

- `sales_analysis` → `ask_data`
- `policy_qa` → `rag`
- `executive_review` → `hybrid`

## API (target)

- CRUD skills + versions
- `POST .../skills/{id}/activate`
- Optional: `GET .../skills/{id}/manifest` for FE display

## FE (target)

Skills list + create wizard (Studio-like) — M3; **not in frontend-dev today**.

## Relation to OSSIE

OSSIE remains the **semantic metric catalog** for structured data skills. Skills choose **which tools and prompts** apply; they do not replace OSSIE YAML.
