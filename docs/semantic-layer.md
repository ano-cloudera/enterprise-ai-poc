# Semantic Layer

The semantic layer is the source of truth for **governed** analytical SQL. Generic backend code does not embed Tempo business synonyms or ad-hoc table names.

## Production path (Ask AI + Dashboard governed mode)

| Item | Location |
|------|----------|
| OSSIE model | `backend/projects/tempo_scan_impala/ossie/tempo_core.ossie.yaml` |
| Governance / ambiguities | `backend/projects/tempo_scan_impala/ossie/tempo_governance.yaml` |
| Golden questions | `backend/projects/tempo_scan_impala/ossie/golden_questions.yaml` |
| Resolver + SQL compile | `backend/app/semantic/` (`TempoOssieRegistry`, `SemanticContextService`) |
| Contract validation | `scripts/validate_tempo_impala_contract.py` |

Default runtime (see `backend/app/core/config.py`):

```env
PROJECT_ID=tempo_scan_impala
DATA_BACKEND=impala
SEMANTIC_EXECUTION_MODE=ossie
```

Metrics declare `base_dataset`, allowed dimensions, and Hive-safe expressions. Follow-up and domain graph hints live in `backend/knowledge/tempo_domain_graph.yaml`.

## Legacy / auxiliary profiles

| Profile | Purpose |
|---------|---------|
| `projects/tempo_scan/` | Synthetic DuckDB semantic YAML, forecast/weather/market fixtures — **not** the live Impala Ask AI path |
| `projects/_template/` | Empty customer template |
| `backend-test/` | Exploratory agent over local DuckDB `silver.*` (port 8001) |

Configuration for legacy YAML is loaded by `app.semantic.loader` where still used (forecast tools, bootstrap). The **live chat governed path** uses OSSIE only.

See also: [`nl-to-sql.md`](nl-to-sql.md), [`tempo-impala-ossie-runbook.md`](tempo-impala-ossie-runbook.md), [`data-enhancement-views.md`](data-enhancement-views.md).
