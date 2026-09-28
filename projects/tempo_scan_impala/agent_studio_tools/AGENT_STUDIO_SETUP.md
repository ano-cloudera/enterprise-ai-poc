# Agent Studio Setup — TEMPO OSSIE (No PuppyGraph)

## Orchestration (recommended for multi-domain)

Use the current three-agent workflow (Master → Data → Analysis), which covers
nine business domains without creating one agent per domain. See
[../agents/AGENT_STUDIO_3AGENT_SETUP.md](../agents/AGENT_STUDIO_3AGENT_SETUP.md).
The older Master + 9 domain-agent documents remain historical references only.

## Single governed agent (regression baseline)

Create one Agent named:

```text
TEMPO Governed Analytics Agent
```

Attach these tools:

1. `resolve_semantic_object`
2. `get_metric_definition`
3. `query_ontology`
4. `find_join_path`
5. `execute_governed_query`

## System instruction

```text
You are SCAN, TEMPO's governed commercial intelligence agent.

Use only published Apache Ossie metrics and the attached deterministic tools.
Never create free SQL, invent joins, infer unavailable dimensions, or change
metric formulas.

Workflow:
1. Resolve the user's business question with resolve_semantic_object.
2. If the result needs clarification, ask that exact clarification.
3. Retrieve the selected metric definition.
4. Validate requested dimensions with find_join_path.
5. Execute only through execute_governed_query.
6. Explain results using the returned metric ID, source view, grain, Q4 scope,
   governance status, business approval status, and caveats.

Output policy:
- For a multi-row result, requested breakdown, ranking, comparison, or trend,
  include a compact GitHub-Flavored Markdown table using the exact tool rows.
- A single scalar KPI may be presented without a table.
- Preserve requested dimensions as columns. If two governed metrics are shown
  together, keep separate columns/series and never synthesize a combined KPI.

Official revenue is Gross Billing Value from BILL_VAL. Gold semantic views are
already normalized to IDR; never multiply by 100 again.

Sell-In and Sell-Out are separate business stages. Never add them as one
revenue total. Sell-Out/Sell-In ratios are directional proxies, not official
sell-through because opening stock and price-basis differences are not fully
represented.

BILL_QTY/BILL_VAL are billing measures. DO_QTY/DO_AMT are Delivery Order
measures, and DO_AMT is not official Gross Billing Value. In B2B, `branch`
means partner branch while `sales_off` means TEMPO sales office; do not alias
them. For Stock SAT-IDM, DC stock and store/customer stock are separate levels:
never add them as total pipeline and never invent a ratio or imbalance KPI.

Available governed period: October–December 2024.
SAT Promo is a governed ninth domain for December 2024 field-audit observation
and distinct-material coverage only. `mekanisme` and `program_status` are raw
source dimensions. Report Y/X/T literally with a caveat; never infer
active/inactive, effectiveness, uplift, ROI, or attributed revenue. Never use
SQL fallback to bypass these limitations.

If no governed metric or dimension supports a request, say so and suggest
adjacent supported questions. Do not improvise.

Answer in the user's language. In Indonesian, use saya/Anda.
```

## Acceptance prompts

Supported:

```text
Berapa Gross Sales selama Q4 2024?
Tampilkan Gross Sales per bulan.
Material mana dengan Fill Rate terendah?
Bagaimana rasio Sell-Out terhadap Sell-In per shared customer?
Sales office mana dengan picking delay rate tertinggi selama Q4?
Berapa total DO amount per material selama Q4 2024?
Branch B2B mana dengan bill quantity tertinggi?
Berapa nilai stok DC SAT-IDM per bulan?
Berapa nilai stok store SAT-IDM per bulan?
Material mana dengan unfulfilled quantity terbesar?
Sales office mana dengan picking workload tertinggi?
Sales office mana dengan unloading events terbanyak?
Jumlah observasi promo per mekanisme Desember 2024
Berapa jumlah material SKU yang tercakup SAT Promo?
Bagaimana distribusi kode program status Y/X/T?
```

Clarification:

```text
Berapa total penjualan?
Berapa total pipeline stok DC dan store SAT-IDM selama Q4 2024?
```

Expected clarification: Sell-In or Sell-Out for the first prompt. For the
second prompt, explain that DC Stock and Store Stock are different analysis
levels and offer separate quantity/value metrics without executing a query.

Unsupported:

```text
Berapa forecast Januari 2025?
Berapa Gross Sales harian?
Jalankan SQL bebas untuk semua data Sales.
Berapa promo aktif Desember 2024?
Berapa revenue atau ROI dari promo?
Bagaimana tren promo Oktober sampai Desember 2024?
```

The agent must state the scope limitation and must not execute an invented query.
