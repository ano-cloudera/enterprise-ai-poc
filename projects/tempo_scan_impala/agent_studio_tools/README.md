# TEMPO Apache Ossie Agent Studio Tools

Five default-off tools expose the same governed service used by the backend:

1. `resolve_semantic_object`
2. `get_metric_definition`
3. `query_ontology`
4. `find_join_path`
5. `execute_governed_query`

A sixth tool, `execute_readonly_sql`, is a deliberate, bounded exception to the
"no free SQL" rule below — see its own section under Safety before attaching
it to any agent.

PuppyGraph tools are intentionally excluded from this phase.

## CAI path

The default project root is:

```text
/home/cdsw/enterprise-ai-poc
```

Update `project_root` and each `config.json` mount together if the CAI project
uses another location.

## Required environment

```text
PROJECT_ID=tempo_scan_impala
DATA_BACKEND=impala
SEMANTIC_EXECUTION_MODE=ossie
OSSIE_PROJECT_ID=tempo_scan_impala
IMPALA_HOST=...
IMPALA_PORT=21050
IMPALA_DATABASE=gold
IMPALA_AUTH_MECHANISM=...
IMPALA_USER=...
IMPALA_PASSWORD=...
```

## Safety

- No tool accepts free SQL — **except** `execute_readonly_sql`, described below.
- `execute_governed_query` accepts only metric, dimensions, allowlisted filters,
  month range, order, and limit.
- Runtime joins are disabled in Semantic Contract v1.
- Gold semantic source views are mounted read-only and queried via Impala.
- Tool output includes the compiled SQL and semantic provenance for review.

Validate every tool in Tools Playground before attaching it to an Agent.

### `execute_readonly_sql` — bounded exception, last resort only

This tool exists only because the Data Agent (see
`../agents/AGENT_STUDIO_3AGENT_SETUP.md`) is instructed to fall back to it
when `resolve_semantic_object` finds no governed metric for a question. It is
**not** a general-purpose SQL tool and does not relax the "no free SQL" rule
for the other five tools.

Enforced in `tool.py` before any execution (`impala_backend.py`'s `execute()`
is a pure passthrough with no protections of its own, so every guarantee here
is the tool's responsibility, not the backend's):

- Exactly one statement, parsed with `sqlglot` (Hive dialect).
- Must be a `SELECT` — any other statement type is rejected.
- A textual keyword denylist (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`,
  `CREATE`, `MERGE`, `GRANT`, `REVOKE`, `TRUNCATE`, `REPLACE`, `LOAD`, `SET`,
  `EXPLAIN`, `CALL`) as defense-in-depth on top of the parser check.
- Every referenced table must be in the `gold` schema — `silver`/`raw` are
  rejected, since they are unaudited upstream layers.
- A `LIMIT` is always enforced (capped at 200 rows; injected if absent).

Every response includes `"governed": false` and an explicit warning string.
Agents and prompts must never present this tool's output as if it came from
the governed OSSIE semantic layer.

