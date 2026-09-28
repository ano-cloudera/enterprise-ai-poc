# TEMPO Showcase Semantic Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand governed TEMPO business-question coverage for the 29 September 2026 showcase using already available Gold views and corrected business semantics.

**Architecture:** Gold views and OSSIE stay authoritative. First add low-risk metrics over datasets already modeled in OSSIE, then inspect and selectively expose additional existing Gold views. Irvan's catalog is used only as definition input; Neo4j, Qdrant, and Semantica are excluded from the showcase runtime.

**Tech Stack:** Apache Ossie YAML, Python 3.12, PyYAML, pytest, Impala SQL, Agent Studio Python tools.

**Spec:** `docs/superpowers/specs/2026-09-28-tempo-showcase-semantic-expansion-design.md`

## Global Constraints

- Do not introduce a Neo4j, Qdrant, or Semantica runtime dependency.
- Use only inspected Gold-view columns; never infer schema from a view name.
- Never combine DC stock and store stock into a total, ratio, or imbalance KPI.
- Preserve existing metric names and IDs; add new metrics without risky showcase-day renames.
- Keep unrelated untracked `datasets/`, `docs/diagrams/`, and ignored `reference/` content intact.

## Review Focus

- A B2B question containing `branch` must group by `branch`, while `sales office` must group by `sales_off`.
- Material DO amount must not resolve to Gross Billing Value or be described as official revenue.
- SAT-IDM questions containing `nilai`/`value` must select value metrics without combining DC and store levels.
- Generic stock wording must continue to request scope clarification rather than guess Stock Tempo versus SAT-IDM.
- Newly admitted Gold views must have verified grains and must not create runtime-invented joins.

---

### Task 1: Extend the existing OSSIE datasets with showcase-safe metrics

**Files:**
- Modify: `projects/tempo_scan_impala/ossie/tempo_core.ossie.yaml`
- Modify: `backend/tests/test_tempo_ossie_service.py`
- Modify: `backend/tests/test_tempo_impala_contract.py`

**Interfaces:**
- Consumes: existing `material_360`, `b2b_branch_estore`, `b2b_material_plu`, `service_level_material`, `sales_office_q4`, and `sat_idm_dc_month` fields.
- Produces: resolvable OSSIE metrics for Material DO, B2B quantity, SAT-IDM values, unfulfilled demand, picking workload, and unloading events.

- [ ] **Step 1: Write failing resolver and compiler tests**

Add literal expectations for the new metric names, metric IDs, source views,
formulas, allowed dimensions, coverage filters, and branch/sales-office
dimension behavior.

- [ ] **Step 2: Run focused tests and verify they fail because the metrics are absent**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_ossie_service.py backend/tests/test_tempo_impala_contract.py`

Expected: failures name the missing metrics or old metric count.

- [ ] **Step 3: Add the minimal metric definitions**

Add unique IDs and aliases while preserving existing names. Use `SUM(PO)-SUM(DO)` for unfulfilled quantity and additive row measures for picking/unloading workload.

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_ossie_service.py backend/tests/test_tempo_impala_contract.py`

Expected: all selected tests pass.

### Task 2: Correct and expand the business-question catalog

**Files:**
- Modify: `datasets/TEMPO_BUSINESS_QUESTIONS_CATALOG.md`
- Modify: `datasets/TEMPO_STOCK_SAT_IDM_FIELD_CATALOG.md`
- Modify: `datasets/TEMPO_DATAMART_PLAN.md`

**Interfaces:**
- Consumes: metric names and IDs produced by Task 1.
- Produces: showcase question inventory that matches the executable OSSIE contract.

- [ ] **Step 1: Reconcile existing question statuses against Task 1 and current allowed dimensions**

Correct Stock Tempo plant coverage, Sales material Bill/DO terminology,
B2B branch versus sales-office wording, and SAT-IDM I08.

- [ ] **Step 2: Add showcase questions for every new metric**

Include totals, ranking, monthly trend, and safe comparison examples. Mark
questions requiring unmodeled grains or joins as `needs_semantic_v2`.

- [ ] **Step 3: Run the contract validator**

Run: `PYTHONPATH=backend .venv/bin/python scripts/validate_tempo_impala_contract.py --json`

Expected: `valid` is `true` and no unknown metric/dimension is reported.

### Task 3: Inspect and selectively admit additional existing Gold views

**Files:**
- Modify if admitted: `projects/tempo_scan_impala/ossie/tempo_core.ossie.yaml`
- Modify if admitted: `projects/tempo_scan_impala/ossie/golden_questions.yaml`
- Modify: `backend/tests/test_tempo_impala_contract.py`
- Create: `datasets/audit/22_showcase_gold_view_contract.sql`

**Interfaces:**
- Consumes: the supplied inventory of existing Gold views.
- Produces: inspected column/grain evidence and only the datasets/metrics that can be safely exposed before the showcase.

- [ ] **Step 1: Write failing contract tests for each view selected after schema inspection**

Tests must assert exact source, primary key, metric formula, and allowed dimensions.

- [ ] **Step 2: Add an audit SQL file for grain uniqueness, nulls, and denominator validity**

Cover the selected Sales customer/office, Picking, Unloading, Promo, or retail views; omit any view whose schema cannot be verified.

- [ ] **Step 3: Add minimal OSSIE datasets and metrics**

No relationships are added unless an audited Gold view already materializes the join.

- [ ] **Step 4: Run contract and service suites**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_impala_contract.py backend/tests/test_tempo_ossie_service.py backend/tests/test_tempo_agent_studio_tools.py`

Expected: all tests pass.

### Task 4: Harden the Agent Studio showcase contract

**Files:**
- Modify: `projects/tempo_scan_impala/ossie/golden_questions.yaml`
- Modify: `projects/tempo_scan_impala/agents/AGENT_STUDIO_3AGENT_SETUP.md`
- Modify: `projects/tempo_scan_impala/agent_studio_tools/AGENT_STUDIO_SETUP.md`
- Modify: `backend/tests/test_tempo_agent_studio_tools.py`

**Interfaces:**
- Consumes: final metrics and datasets from Tasks 1 and 3.
- Produces: tested showcase questions and deployment instructions consistent with the governed contract.

- [ ] **Step 1: Add failing end-to-end tool-resolution tests**

Cover Material Bill/DO, B2B branch, B2B sales office, SAT-IDM DC/store value,
Service Level gap, Picking workload, and Unloading events.

- [ ] **Step 2: Update golden questions and Agent Studio prompts**

Describe supported operational domains without claiming unsupported SAT Promo or cross-grain joins.

- [ ] **Step 3: Run the full relevant regression suite**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_impala_contract.py backend/tests/test_tempo_ossie_service.py backend/tests/test_tempo_agent_studio_tools.py backend/tests/test_tempo_ossie_graph_nodes.py`

Expected: all tests pass.

### Task 5: Record the post-showcase Semantica spike

**Files:**
- Create: `docs/SEMANTICA_ASSESSMENT.md`

**Interfaces:**
- Consumes: the final canonical OSSIE metric catalog and findings from Irvan's catalog.
- Produces: a non-runtime assessment covering architecture, reuse, effort, security, success metrics, and a go/no-go experiment.

- [ ] **Step 1: Document the bounded spike**

Specify verified-catalog ingestion, provenance/versioning evaluation, optional Neo4j/Qdrant backends, resolver accuracy/latency comparison, CrewAI dependency/security review, and rollback criteria.

- [ ] **Step 2: Verify documentation references current metric names and no secrets**

Run: `rg -n "password|api[_-]?key|bearer|secret|token" docs/SEMANTICA_ASSESSMENT.md`

Expected: no credential values or setup secrets are present.
