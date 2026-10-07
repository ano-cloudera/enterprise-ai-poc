# TEMPO Full-Domain Governed Metric Coverage Design

**Date:** 28 September 2026
**Status:** Approved design direction; implementation plan pending review
**Runtime authority:** Gold views + Apache Ossie
**Deferred component:** Semantica, after Agent Studio baseline acceptance

## 1. Objective

Expand TEMPO Commercial Intelligence so Agent Studio handles the full known
business-question surface across all nine domains while preserving governed,
deterministic execution.

The implementation covers:

1. Sales / Sell-In
2. B2B / Sell-Out
3. Stock Tempo
4. Stock SAT-IDM
5. SAT OOS
6. Service Level
7. Picking
8. Unloading
9. SAT Promo

Coverage means every known question has an explicit outcome. It does not mean
inventing data or forcing every question into a metric.

## 2. Coverage Definition

The acceptance corpus starts with all 165 catalog questions and expands each
applicable metric into common user variants:

- total and company-level summary;
- monthly trend and period comparison;
- top/bottom ranking;
- breakdown by every allowed dimension;
- exact filters and period restrictions;
- metric comparison when both measures share an audited grain;
- Indonesian and English aliases;
- context-dependent follow-up questions;
- ambiguity, unsupported, and unsafe-query controls.

Every question or variant must end in one of these statuses:

| Status | Meaning |
|---|---|
| `governed` | Gold contract and OSSIE metric are approved and executable. |
| `governed_with_caveat` | Executable, but the response must preserve a documented limitation. |
| `candidate` | Technically modeled but awaiting business approval; not presented as final. |
| `needs_gold_contract` | Source data exists but no audited Gold grain supports the request yet. |
| `needs_clarification` | The user must choose a business stage, stock scope, unit, or dimension. |
| `unsupported` | Required data or business definition is absent, or the request is out of scope. |
| `rejected` | Unsafe or prohibited operation such as arbitrary write SQL. |

Coverage is complete when no catalog question has an unknown or accidental
fallback outcome.

## 3. Source-of-Truth Hierarchy

The layers have non-overlapping authority:

```text
Raw / Silver
    |
    v
Gold view contracts
    |
    v
Apache Ossie canonical metrics
    |
    v
Agent Studio governed tools
    |
    v
Frontend response and visualization
```

- Gold owns physical columns, grain, normalization, and materialized joins.
- OSSIE owns metric names, formulas, units, allowed dimensions, filters,
  governance status, aliases, and business instructions.
- Irvan's catalog is candidate metadata. It cannot override Gold or OSSIE.
- Agent Studio orchestrates resolution, execution, and explanation; it cannot
  invent formulas, tables, dimensions, or joins.
- Semantica is deferred and may later provide ontology, provenance, and
  candidate retrieval. It will not become the metric execution authority.

## 4. Catalog Reconciliation

A deterministic reconciliation tool compares the current OSSIE registry with
Irvan's KPI/query catalog.

Each Irvan KPI receives one classification:

| Classification | Promotion behavior |
|---|---|
| `exact_match` | Link provenance; do not create a duplicate metric. |
| `alias_duplicate` | Add a tested alias only when it cannot collide. |
| `safe_candidate` | Eligible for Gold audit and OSSIE promotion. |
| `needs_gold_audit` | Formula appears useful but the physical view/grain is unverified. |
| `definition_conflict` | Record both definitions and require business resolution. |
| `unsupported_source` | Source, unit, or required fields are absent. |
| `excluded` | Unsafe, obsolete, unapproved, or contrary to confirmed TEMPO semantics. |

The tool produces machine-readable JSON plus a reviewer-friendly Markdown
report. It never edits OSSIE automatically.

## 5. Gold Contract Registry

Every view considered for OSSIE must have an auditable contract containing:

- deployed view name;
- physical columns and types;
- primary grain;
- reporting period;
- additive, semi-additive, and non-additive measures;
- null counts and duplicate-grain counts;
- valid denominator and range checks;
- normalization rules;
- source Silver table;
- approved join keys and measured join coverage;
- data owner and approval status.

The contract-audit SQL is read-only. A view is not admitted based only on its
name or its presence in the Irvan catalog.

Initial unverified priority views include:

- `gold.corr_sales_material_total`
- `gold.corr_sales_customer_month`
- `gold.corr_sales_sales_office`
- `gold.rpt_picking_status_summary`
- `gold.corr_sat_promo_materials`
- additional Service Level, Stock Tempo, Picking, and Unloading views from the
  supplied environment inventory.

## 6. Metric Promotion Pipeline

Promotion is domain-by-domain but uses one common gate:

1. Select an unmet business question cluster.
2. Confirm the source Gold contract.
3. Define the minimal reusable metric primitive.
4. Define units, dimensions, filters, caveats, and approval status.
5. Write resolver collision and query compiler tests.
6. Add the OSSIE metric without renaming existing published metrics.
7. Add golden questions and user-language variants.
8. Validate against Agent Studio tools.
9. Promote to `governed` only after technical and business gates pass.

One reusable metric should answer multiple question forms. Total, trend,
ranking, and filter variants do not become separate metrics unless their
formula or grain is genuinely different.

## 7. Non-Negotiable Business Semantics

The following rules apply across every domain:

- `BILL_QTY` and `BILL_VAL` are billing quantity and billing amount.
- `DO_QTY` and `DO_AMT` are Delivery Order quantity and amount.
- `DO_AMT` is not official Gross Billing Value.
- B2B `branch` and TEMPO `sales_off` are distinct dimensions.
- Material and PLU remain independent dimensions until an official mapping is
  approved.
- Stock Tempo represents internal Tempo warehouse stock.
- SAT-IDM DC Stock and Store Stock are different analysis levels. They must
  never be added into total pipeline or converted into an unapproved ratio or
  imbalance KPI.
- SAT OOS represents field audit availability at evaluated DC/B2B units.
- Picking and Unloading row counts are operational workloads, not product
  quantities or distinct documents unless the Gold contract proves otherwise.
- SAT Promo is December-only unless additional periods are physically present
  and audited.
- No runtime-invented joins and no arbitrary write SQL are allowed.

## 8. Question Coverage Compiler

The question catalog becomes an executable coverage matrix rather than only a
Markdown inventory.

For each question it records:

- domain and question ID;
- expected status;
- canonical metric or blocker;
- source dataset and view;
- allowed dimensions and filters;
- chart recommendation;
- required caveat;
- accepted paraphrases;
- expected tool path;
- whether SQL fallback is prohibited or permitted as explicitly ungoverned.

The compiler generates deterministic tests for resolver selection, metric ID,
dataset, dimensions, and refusal behavior. Human-reviewed edge cases remain as
explicit test fixtures.

## 9. Agent Studio Acceptance

The final pre-Semantica gate runs the production three-agent workflow against
a balanced suite covering every domain and outcome class.

Acceptance measures:

| Measure | Required result |
|---|---|
| Governed metric selection | At least 95% on approved paraphrase corpus |
| Safety-critical ambiguity/refusal | 100% |
| Runtime-invented metric/join | 0 |
| Governed answer provenance | Metric ID, source view, grain, period, and caveat present |
| Tool path | Combined governed tool preferred; fallback only where explicitly allowed |
| Follow-up preservation | Metric, dimensions, filters, and period preserved correctly |
| Response quality | Business-readable answer with technical details hidden by default |
| Reliability | Repeated execution produces stable routing and status |

Safety-critical cases include Billing versus Delivery Order, Sell-In versus
Sell-Out, branch versus sales office, Stock Tempo versus SAT-IDM, DC versus
Store Stock, and governed versus ungoverned execution.

## 10. Error Handling

- Missing or changed Gold columns fail contract validation before deployment.
- Duplicate metric IDs fail registry validation.
- Alias collisions fail resolver tests.
- Missing business approval retains `candidate` status.
- Query/backend failures return a safe technical status and never fabricate
  data.
- Unsupported questions return the closest safe alternatives.
- Agent Studio test failures block catalog freeze and Semantica work.

## 11. Deliverables

1. OSSIE-versus-Irvan reconciliation tool and reports.
2. Gold contract registry and read-only audit SQL for all candidate views.
3. Expanded OSSIE datasets and metrics for all technically supportable gaps.
4. Executable coverage matrix for the 165 questions and their variants.
5. Updated golden questions and Agent Studio instructions.
6. Domain-balanced automated and live Agent Studio acceptance report.
7. Frozen baseline catalog export for the later Semantica experiment.

## 12. Semantica Final Phase

Semantica begins only after:

- all nine domains have explicit coverage outcomes;
- selected Gold contracts pass audit;
- OSSIE tests and Agent Studio acceptance pass;
- the catalog baseline is versioned and frozen.

Semantica first runs offline and then in shadow mode. Its output is compared
against the frozen OSSIE baseline. Production promotion requires no regression
in routing accuracy, safety, provenance, or latency, and must remain removable
without changing the Agent Studio API contract.

No separate Cloudera AI Application is required for the initial Semantica
experiment. Development uses an isolated environment in the existing project;
a separate long-running service or model deployment is considered only after
shadow-mode acceptance.

## 13. Explicit Non-Goals

- Claiming that every imaginable natural-language question is answerable.
- Turning unsupported source data into speculative metrics.
- Automatically importing all Irvan KPIs into OSSIE.
- Adding Neo4j, Qdrant, or Semantica to the current Agent Studio runtime.
- Replacing Gold views or OSSIE with an LLM-generated semantic layer.
- Hiding pending business approvals from end users or reviewers.
