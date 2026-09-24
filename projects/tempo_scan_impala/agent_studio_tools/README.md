# TEMPO Apache Ossie Agent Studio Tools

Five default-off tools expose the same governed service used by the backend:

1. `resolve_semantic_object`
2. `get_metric_definition`
3. `query_ontology`
4. `find_join_path`
5. `execute_governed_query`

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

- No tool accepts free SQL.
- `execute_governed_query` accepts only metric, dimensions, allowlisted filters,
  month range, order, and limit.
- Runtime joins are disabled in Semantic Contract v1.
- Gold semantic source views are mounted read-only and queried via Impala.
- Tool output includes the compiled SQL and semantic provenance for review.

Validate every tool in Tools Playground before attaching it to an Agent.

