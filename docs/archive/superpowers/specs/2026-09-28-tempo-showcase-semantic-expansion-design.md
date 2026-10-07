# TEMPO Showcase Semantic Expansion Design

## Objective

Expand the governed business-question coverage for the 29 September 2026
showcase using Gold views that already exist, while preserving OSSIE as the
metric and governed-query source of truth.

## Architecture decision

- Gold views remain the authoritative analytical data layer.
- OSSIE remains the authoritative metric, dimension, grain, and governed SQL
  contract used by Agent Studio.
- Irvan's 66-KPI catalog is a candidate-definition source only. Definitions
  are adopted only after their source view, formula, grain, unit, and current
  TEMPO terminology are verified.
- Irvan's Neo4j and Qdrant services are not runtime dependencies for the
  showcase.
- Semantica is not introduced into the showcase runtime. It will be assessed
  afterward as an optional metadata, provenance, ontology, and retrieval
  overlay; it does not replace Gold views or OSSIE query compilation.

## Business semantics

### Sales / Sell-In

- `material` is a product dimension.
- `bill_qty` is billed/sold quantity.
- `bill_val` is billed amount and the official Gross Billing Value in IDR.
- `do_qty` is Delivery Order quantity.
- `do_amt` is Delivery Order amount in IDR and must not be labeled official
  revenue.
- Material-level Bill and DO metrics use the existing
  `gold.rpt_sap_material_month_semantic` dataset.

### B2B branch and sales office

- `branch` and `sales_off` are separate dimensions.
- `branch` is a B2B partner branch/DC.
- `sales_off` is a TEMPO sales-office attribution on B2B data.
- `bill_qty` and `bill_val` are measures, never dimensions.
- The requested dimension determines the grouping; it does not change the
  underlying B2B billing measure.

### Stock SAT-IDM

- DC stock and store/customer stock represent different analytical levels.
- Publish DC quantity/value and store quantity/value as four separate metrics.
- Never sum them into a `total pipeline` metric.
- Do not publish store-to-DC ratio or pipeline imbalance as official KPIs.
- Side-by-side presentation is allowed when clearly labeled as two levels.

### Operational domains

- Prefer additive metrics that can be calculated from existing Gold fields.
- Weighted rates must be recomputed from numerator and denominator when those
  fields exist; do not average percentages.
- Do not infer mappings between Plant, sales office, partner branch, DC, PLU,
  and Material unless an audited Gold view already implements the mapping.

## Showcase scope

### P0: semantic-only expansion over already modeled datasets

- Material DO quantity and amount.
- B2B bill quantity by branch, sales office, e-store, material, and PLU where
  the corresponding modeled dataset permits it.
- SAT-IDM DC value and store value.
- Service Level unfulfilled quantity.
- Picking workload rows.
- Unloading event rows.
- Catalog corrections for Stock Tempo `plant` and SAT-IDM separated levels.

### P1: expose additional existing Gold views

Candidate views include:

- `corr_sales_customer_month`
- `corr_sales_sales_office`
- `corr_picking_sales_office`
- `corr_unloading_sales_office`
- `corr_sat_promo_materials`
- `rpt_picking_status_summary`
- `rpt_sat_retail_material_month`
- `rpt_semantic_metric_catalog`

Each view is admitted only after its columns and grain are inspected. No field
or business definition may be guessed from the view name alone.

## Semantica decision

For the showcase, Semantica is deferred. A post-showcase spike may ingest the
canonical metric catalog as verified seed data and evaluate ontology,
provenance, versioning, conflict detection, and hybrid graph/vector retrieval.
The spike must not put Semantica or any graph/vector service on the governed
query execution critical path until measured against OSSIE resolution
accuracy, latency, availability, and security requirements.

## Acceptance criteria

- New metrics compile to audited `gold.*` sources only.
- Metric IDs are unique and dimensions are allowlisted.
- Regression questions resolve branch and sales office to different
  dimensions.
- No governed metric adds or ratios DC stock and store stock.
- Existing OSSIE contract, service, and Agent Studio tool tests remain green.
- Showcase questions include simple totals, rankings, monthly trends, and
  cross-domain insights without unsupported joins.
