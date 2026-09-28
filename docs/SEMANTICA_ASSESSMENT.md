# Semantica Assessment for TEMPO Commercial Intelligence

**Decision for the 29 September 2026 showcase:** do not add Semantica,
Neo4j, or Qdrant to the production request path. Keep existing Gold views and
Apache Ossie as the authoritative metric contract.

**Recommended next step:** run a bounded, offline Semantica spike after the
showcase. Use it to evaluate catalog ingestion, ontology/provenance management,
and retrieval quality—not to replace governed SQL or Gold data products.

## Why this boundary is appropriate

The current runtime already has the capabilities required for a stable demo:

- Gold views hold audited physical data and materialized cross-domain joins.
- Apache Ossie publishes canonical formulas, units, allowed dimensions,
  approval status, and business terminology.
- Agent Studio exposes one combined governed metric query tool and streams
  progress to the frontend.
- The current contract contains 14 datasets and 48 governed metrics covering
  eight domains; SAT Promo remains outside the runtime until its Gold schema is
  audited.

Semantica offers modules for ingestion, knowledge graphs, ontology/provenance,
semantic search, and agent integrations. Those features can improve catalog
maintenance and discovery, but they do not remove the need for audited Gold
views, stable grains, approved metric formulas, or deterministic query
compilation.

Primary references:

- Modules: <https://docs.getsemantica.ai/modules/>
- Architecture: <https://docs.getsemantica.ai/architecture/>
- CrewAI integration: <https://docs.getsemantica.ai/integrations/crewai/>
- MCP integration: <https://docs.getsemantica.ai/guides/mcp-server/>
- License: <https://docs.getsemantica.ai/project-license/>

## What to reuse from Irvan

Reuse definitions as candidate metadata only:

- KPI name, business definition, unit, aliases, and example questions.
- Candidate dimension names and domain taxonomy.
- Provenance hints pointing to Gold/Silver sources.
- Query examples as audit inputs.

Do not automatically import:

- Neo4j or Qdrant runtime topology.
- A `governed` label without verifying the physical Gold view.
- Formulas that query Silver directly when a canonical Gold view is required.
- Inferred joins, grains, or aliases that conflict with Tempo confirmations.
- Credentials, endpoints, or configuration values from reference files.

Every candidate must pass this promotion checklist before entering OSSIE:

1. Physical source view exists.
2. Columns and data types are recorded from the deployed environment.
3. Grain uniqueness and null behavior are measured.
4. Formula, numerator/denominator, unit, and period are explicit.
5. Allowed dimensions are supported by the same audited view.
6. Business approval status and owner are recorded.
7. Resolver aliases pass collision tests against existing metrics.

## Proposed bounded spike

### Scope

Use a read-only export of the current OSSIE catalog plus a sanitized subset of
Irvan's KPI definitions. Start with three representative domains:

- Sales Material: billing versus Delivery Order terminology.
- B2B: branch versus TEMPO sales office.
- Stock SAT-IDM: DC versus store/customer levels.

These domains deliberately include the ambiguity cases that matter most to
TEMPO and therefore provide a meaningful test of ontology and provenance.

### Architecture

```text
Gold views ──> OSSIE canonical catalog ──> deterministic query compiler
                    │
                    └──> catalog export ──> Semantica experiment
                                               │
Irvan definitions (sanitized, candidate only) ─┘
```

Semantica may write its experiment state to an isolated local backend first.
Neo4j or Qdrant should only be tested as optional storage adapters if the local
experiment demonstrates value. The frontend and Agent Studio production path
must remain unchanged during the spike.

### Evaluation set

Build an evaluation set from:

- the OSSIE golden questions;
- the showcase questions added on 28 September 2026;
- ambiguous and negative-control questions;
- selected candidate questions from Irvan's catalog.

Measure:

| Metric | Baseline | Go threshold |
|---|---:|---:|
| Canonical metric selection accuracy | Current OSSIE resolver | No regression; target at least 95% on approved questions |
| Ambiguity/refusal precision | Current deterministic gates | 100% on safety-critical cases |
| Added p95 routing latency | 0 ms | At most 500 ms |
| Unsupported metric hallucination | 0 accepted by compiler | 0 |
| Provenance completeness | OSSIE fields | Source, grain, formula, unit, approval on every answer |
| Catalog-maintenance effort | Manual YAML baseline | Material reduction demonstrated on one catalog update |

Safety-critical cases include:

- `BILL_VAL` must not be confused with `DO_AMT`.
- `BILL_QTY` must not be confused with `DO_QTY`.
- B2B `branch` must not be aliased to `sales_off`.
- DC Stock and Store Stock must never be summed into total pipeline or turned
  into an unapproved ratio/imbalance KPI.

### Security and dependency gate

Before any integration:

1. Generate a dependency lock and software bill of materials.
2. Scan Semantica and its optional integrations for known vulnerabilities.
3. Review the CrewAI integration separately; its documentation currently
   warns about critical unpatched advisories in its CrewAI/ChromaDB dependency
   path.
4. Keep source credentials and deployed endpoints outside experiment data.
5. Rotate any live-looking credentials found in reference material and notify
   the owner through the appropriate internal channel.
6. Run with read-only catalog/data access and no ability to execute free SQL.

## Effort estimate

Assuming the Gold views and all nine domain definitions have already been
audited:

| Work | Estimate |
|---|---:|
| Canonical OSSIE export and Irvan-catalog sanitizer | 1–2 days |
| Semantica local ingestion and ontology/provenance mapping | 2–3 days |
| Evaluation harness and ambiguity cases | 2–3 days |
| Optional Neo4j/Qdrant adapter comparison | 1–2 days |
| Security/dependency review and findings | 1–2 days |
| Agent Studio shadow-mode adapter | 2–3 days |

Total: approximately **7–13 engineering days** for an evidence-backed spike,
or **3–5 days** for a narrower catalog-only proof of concept. Productionizing
it would require additional operational ownership, monitoring, backup,
versioning, and rollback work.

## Go / no-go decision

Proceed beyond the spike only if Semantica:

- improves catalog discovery or maintenance measurably;
- preserves deterministic OSSIE enforcement;
- meets the accuracy, latency, provenance, and security thresholds above;
- can be removed without changing the Agent Studio API contract.

Stop or keep it offline if it introduces another runtime dependency without a
measured accuracy/maintenance gain, requires bypassing Gold/OSSIE, creates
unapproved joins/formulas, or cannot meet the dependency-security gate.

The fallback is simple: retain the current Gold + OSSIE runtime and use the
Semantica output only as a human-reviewed catalog-authoring aid.
