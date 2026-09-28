# SAT Promo Ninth Governed Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote SAT Promo into the ninth Agent Studio domain with two safe, December-only governed metrics: field-audit observation count and distinct promotional material count.

**Architecture:** Audit the deployed SAT Promo Gold contract first, then publish one normalized semantic Gold view at `reporting_month + material_code + mekanisme + program_status` grain. Apache Ossie remains the metric authority; Agent Studio may report raw `program_status` codes but cannot infer their business meaning, causal uplift, ROI, revenue attribution, or joins.

**Tech Stack:** Impala SQL, Apache Ossie YAML, Python 3.12, PyYAML, sqlglot, pytest, Cloudera Agent Studio.

**Spec:** `docs/superpowers/specs/2026-09-28-tempo-full-domain-metric-coverage-design.md`

## Global Constraints

- SAT Promo is field-audit data for December 2024, not SAP pricing or discounts.
- `program_status` values `X`, `Y`, and `T` may be exposed only as raw dimension codes; no active/inactive label may be inferred until TEMPO confirms the mapping.
- Do not claim promo effectiveness, uplift, ROI, causal impact, or attributed revenue.
- Do not invent joins to Sales, B2B, SAT OOS, SAT-IDM, Picking, or Unloading at runtime.
- `mekanisme` values may be shown only as raw observed categories until TEMPO approves their business labels.
- Existing published metric names and IDs must remain unchanged.
- The deployed physical contract must pass `DESCRIBE`, grain, null, period, and non-negative-count checks before OSSIE admission.
- Semantica, Neo4j, and Qdrant remain outside this implementation and runtime.

## Review Focus

- A question asking for raw `program_status` distribution may be answered with a caveat; “promo aktif” must remain unsupported until TEMPO confirms which code, if any, means active.
- A question asking “revenue/ROI/uplift dari promo” must remain unsupported and must not resolve to Gross Sales.
- A query outside December 2024 must return a period limitation, not fabricate monthly history.
- Blank or null `mekanisme` must be normalized to `UNKNOWN`, while raw nonblank category text is preserved.
- Duplicate source observations must remain observations; only `promo_material_count` deduplicates by material.

---

### Task 1: Audit and freeze the SAT Promo physical contract

**Files:**
- Create: `datasets/audit/23_sat_promo_gold_contract.sql`
- Create: `datasets/qa/23_sat_promo_gold_contract.md`
- Modify: `backend/tests/test_tempo_impala_contract.py`

**Interfaces:**
- Consumes: deployed `gold.corr_sat_promo_materials`, `silver.sat_promo_des_24`, and the confirmed December 2024 business scope.
- Produces: a recorded contract containing exact physical columns, types, row count, December range, null counts, `material_code` cardinality, raw `mekanisme` values, and the approved source for Task 2.

- [ ] **Step 1: Write the failing contract-evidence test**

Add `test_sat_promo_contract_evidence_is_recorded_before_admission()` asserting that:

```python
audit = (ROOT / "datasets/audit/23_sat_promo_gold_contract.sql").read_text()
evidence = (ROOT / "datasets/qa/23_sat_promo_gold_contract.md").read_text()
assert "DESCRIBE gold.corr_sat_promo_materials;" in audit
assert "DESCRIBE silver.sat_promo_des_24;" in audit
assert "TGL_DCP" in evidence
assert "material_code" in evidence
assert "Mekanisme" in evidence
assert "program_status is raw and unmapped" in evidence
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_impala_contract.py::test_sat_promo_contract_evidence_is_recorded_before_admission`

Expected: FAIL because the audit and evidence files do not exist.

- [ ] **Step 3: Add read-only audit SQL**

Create queries for both candidate sources that return:

- exact schema via `DESCRIBE`;
- total rows and distinct material codes;
- minimum and maximum `tgl_dcp`;
- null/blank counts for date, material, and mechanism;
- duplicate counts at observation identity and at `month + material + mechanism` grain;
- raw `mekanisme` and `program_status` distributions, with a comment that `program_status` is a raw, unmapped dimension.

- [ ] **Step 4: Execute the SQL in the Cloudera Workbench and record evidence**

Record the unedited result summary in `datasets/qa/23_sat_promo_gold_contract.md`, including execution timestamp, environment, source chosen, exact source columns, and a PASS/FAIL line for each check. Do not record credentials or cookies.

Hard gate: continue only if the source contains an auditable December date, material identifier, and mechanism. If any required field is absent, stop this plan and keep SAT Promo unsupported until the Gold view is rebuilt from an evidenced source.

- [ ] **Step 5: Run the focused test and verify it passes**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_impala_contract.py::test_sat_promo_contract_evidence_is_recorded_before_admission`

Expected: PASS, and the evidence document says all admission checks passed.

- [ ] **Step 6: Commit the audit evidence**

```bash
git add datasets/audit/23_sat_promo_gold_contract.sql datasets/qa/23_sat_promo_gold_contract.md backend/tests/test_tempo_impala_contract.py
git commit -m "test: audit SAT Promo gold contract"
```

### Task 2: Publish the canonical December SAT Promo semantic view

**Files:**
- Create: `datasets/gold/23_rpt_sat_promo_material_december_semantic.sql`
- Modify: `datasets/audit/23_sat_promo_gold_contract.sql`
- Modify: `backend/tests/test_tempo_impala_contract.py`

**Interfaces:**
- Consumes: the passing physical mapping recorded by Task 1.
- Produces: `gold.rpt_sat_promo_material_december_semantic` with exact grain `(reporting_month, material_code, mekanisme, program_status)` and columns `reporting_month INT`, `material_code STRING`, `mekanisme STRING`, `program_status STRING`, and `promo_observation_count BIGINT`.

- [ ] **Step 1: Write the failing canonical-view contract test**

Add `test_sat_promo_semantic_view_has_safe_december_contract()` asserting the DDL contains:

```python
assert "DROP VIEW IF EXISTS gold.rpt_sat_promo_material_december_semantic;" in ddl
assert "CREATE VIEW gold.rpt_sat_promo_material_december_semantic AS" in ddl
assert "CREATE OR REPLACE VIEW" not in ddl
assert "202412 AS reporting_month" in ddl
assert "COUNT(*) AS promo_observation_count" in ddl
assert "GROUP BY" in ddl
assert "program_status" in ddl.lower()
```

Also assert the post-create audit includes `DESCRIBE gold.rpt_sat_promo_material_december_semantic;`, a duplicate-grain check, and a negative-count check.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_impala_contract.py::test_sat_promo_semantic_view_has_safe_december_contract`

Expected: FAIL because the DDL file is absent.

- [ ] **Step 3: Implement the canonical view using Task 1's exact column mapping**

Use Impala-compatible `DROP VIEW IF EXISTS` followed by `CREATE VIEW`. Normalize material with `TRIM(CAST(... AS STRING))`, normalize blank/null mechanism with `COALESCE(NULLIF(TRIM(CAST(... AS STRING)), ''), 'UNKNOWN')`, normalize blank/null status to `UNKNOWN`, filter only 1–31 December 2024 using the audited date expression, group by month/material/mechanism/status, and count source observations. Do not translate `X`, `Y`, or `T` into business labels.

- [ ] **Step 4: Deploy and validate the view in Workbench**

Run the DDL followed by the post-create audit. Expected: one row per exact grain, `reporting_month = 202412` only, no null material, no negative observation count, raw status values are preserved, and total aggregated observations equal the filtered source row count.

- [ ] **Step 5: Run the focused test and verify it passes**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_impala_contract.py::test_sat_promo_semantic_view_has_safe_december_contract`

Expected: PASS.

- [ ] **Step 6: Commit the canonical view**

```bash
git add datasets/gold/23_rpt_sat_promo_material_december_semantic.sql datasets/audit/23_sat_promo_gold_contract.sql backend/tests/test_tempo_impala_contract.py
git commit -m "feat: add SAT Promo semantic gold view"
```

### Task 3: Add the SAT Promo dataset and two governed OSSIE metrics

**Files:**
- Modify: `projects/tempo_scan_impala/ossie/tempo_core.ossie.yaml`
- Modify: `projects/tempo_scan_impala/ossie/tempo_governance.yaml`
- Modify: `scripts/validate_tempo_impala_contract.py`
- Modify: `backend/tests/test_tempo_impala_contract.py`
- Modify: `backend/tests/test_tempo_ossie_service.py`

**Interfaces:**
- Consumes: `gold.rpt_sat_promo_material_december_semantic` from Task 2.
- Produces: dataset `sat_promo_material_december`; metrics `promo_observation_count` (`PR-03`) and `promo_material_count` (`PR-02`).

- [ ] **Step 1: Write failing registry, resolver, and compiler tests**

Assert all of the following exact contracts:

```python
expected = {
    "promo_observation_count": (
        "SUM(sat_promo_material_december.promo_observation_count)",
        "PR-03",
        ["reporting_month", "material_code", "mekanisme", "program_status"],
    ),
    "promo_material_count": (
        "COUNT(DISTINCT sat_promo_material_december.material_code)",
        "PR-02",
        ["reporting_month", "mekanisme", "program_status"],
    ),
}
```

The dataset must use primary key `[reporting_month, material_code, mekanisme, program_status]`, fixed time scope `[202412]`, and source `gold.rpt_sat_promo_material_december_semantic`. Both metrics use unit `count`, governance status `approved_candidate_with_caveat`, and business approval status `pending_business_confirmation`.

Add resolver assertions that “jumlah observasi promo per mekanisme” selects `promo_observation_count`, “berapa SKU/material promo” selects `promo_material_count`, “distribusi kode program status” selects `promo_observation_count` with `program_status`, and “promo aktif” does not select either metric.

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_impala_contract.py backend/tests/test_tempo_ossie_service.py`

Expected: failures report the missing dataset, metrics, source, aliases, and old counts of 14 datasets/48 metrics.

- [ ] **Step 3: Add the dataset and metrics to OSSIE**

Add labels, aliases in Indonesian and English, raw-mechanism and raw-status caveats, December-only instructions, provenance to Irvan KPI IDs `PR-02`/`PR-03`, and explicit prohibitions against interpreting observations as active/approved promos. Do not add relationships.

- [ ] **Step 4: Extend governance and static validation**

Add SAT Promo ambiguity/refusal language to `tempo_governance.yaml`; add the semantic source to `EXPECTED_SOURCES`; update exact test expectations to 15 datasets and 50 metrics. Ensure the validator accepts `COUNT(DISTINCT ...)` through sqlglot without special-case SQL rewriting.

- [ ] **Step 5: Run focused tests and verify they pass**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_impala_contract.py backend/tests/test_tempo_ossie_service.py`

Expected: all selected tests pass; validator reports 15 datasets and 50 metrics.

- [ ] **Step 6: Commit the semantic contract**

```bash
git add projects/tempo_scan_impala/ossie/tempo_core.ossie.yaml projects/tempo_scan_impala/ossie/tempo_governance.yaml scripts/validate_tempo_impala_contract.py backend/tests/test_tempo_impala_contract.py backend/tests/test_tempo_ossie_service.py
git commit -m "feat: govern SAT Promo as ninth domain"
```

### Task 4: Promote safe Promo questions and preserve refusals

**Files:**
- Modify: `projects/tempo_scan_impala/ossie/golden_questions.yaml`
- Modify: `datasets/TEMPO_BUSINESS_QUESTIONS_CATALOG.md`
- Modify: `datasets/TEMPO_SAT_PROMO_FIELD_CATALOG.md`
- Modify: `backend/tests/test_tempo_agent_studio_tools.py`

**Interfaces:**
- Consumes: the dataset and metrics from Task 3.
- Produces: executable Promo acceptance cases for P01 and P03 plus deterministic refusals for status, attribution, and out-of-period questions.

- [ ] **Step 1: Write failing question-resolution tests**

Add cases for:

- `Jumlah observasi promo per mekanisme Desember 2024` → `promo_observation_count`, dimension `mekanisme`;
- `Berapa jumlah material/SKU yang tercakup SAT Promo?` → `promo_material_count`;
- `Material mana paling sering muncul dalam observasi promo?` → `promo_observation_count`, dimension `material_code`;
- `Bagaimana distribusi kode program status Y/X/T?` → `promo_observation_count`, dimension `program_status`, with an unmapped-code caveat;
- `Berapa promo aktif?` → unsupported because no status code has an approved active meaning;
- `Berapa revenue atau ROI dari promo?` → unsupported because attribution/cost is unavailable;
- `Bagaimana tren promo Oktober–Desember?` → unsupported/clarification because only December exists.

- [ ] **Step 2: Run tests and verify they fail**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_agent_studio_tools.py`

Expected: safe Promo questions are still unsupported or unresolved.

- [ ] **Step 3: Update golden questions and business catalogs**

Promote P01, P02, and P03 to `governed_v1_with_caveat`; add the material-count question as governed coverage; keep P10 and all active/inactive, ROI, attribution, and cross-domain interpretations unsupported or `needs_semantic_v2`. Replace obsolete “no Gold view at all” blockers with the remaining exact blocker, such as missing join, unapproved status meaning, or absent cost data.

- [ ] **Step 4: Run tests and validator and verify they pass**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_agent_studio_tools.py backend/tests/test_tempo_impala_contract.py && PYTHONPATH=backend .venv/bin/python scripts/validate_tempo_impala_contract.py --json`

Expected: tests pass; validator returns `"valid": true`, `"datasets": 15`, `"metrics": 50`, and at least 75 golden questions.

- [ ] **Step 5: Commit question coverage**

```bash
git add projects/tempo_scan_impala/ossie/golden_questions.yaml datasets/TEMPO_BUSINESS_QUESTIONS_CATALOG.md datasets/TEMPO_SAT_PROMO_FIELD_CATALOG.md backend/tests/test_tempo_agent_studio_tools.py
git commit -m "test: cover safe SAT Promo questions"
```

### Task 5: Expose nine domains in Agent Studio and run live acceptance

**Files:**
- Modify: `projects/tempo_scan_impala/agents/AGENT_STUDIO_3AGENT_SETUP.md`
- Modify: `projects/tempo_scan_impala/agent_studio_tools/AGENT_STUDIO_SETUP.md`
- Create: `docs/qa/2026-09-28-agent-studio-nine-domain-acceptance.md`

**Interfaces:**
- Consumes: the frozen 15-dataset/50-metric contract and question cases from Task 4.
- Produces: a deployable nine-domain Agent Studio configuration and recorded UI/API acceptance evidence.

- [ ] **Step 1: Add a failing documentation-contract test**

In `backend/tests/test_tempo_agent_studio_tools.py`, assert the three-agent setup lists all nine domains, no longer says SAT Promo is outside the workflow, and includes the safe Promo happy-path prompt plus the status/ROI refusal prompts.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_tempo_agent_studio_tools.py`

Expected: FAIL on the old eight-domain/SAT-Promo-unsupported wording.

- [ ] **Step 3: Update deployment instructions and prompts**

Add SAT Promo to Master/Data/Analysis Agent scope. Require business-readable tables for dimensioned results, always show December-only and raw-mechanism caveats, and hide internal status keys/SQL unless troubleshooting. Preserve the combined governed tool path and never permit SQL fallback to reinterpret `program_status`.

- [ ] **Step 4: Run local regression before deployment**

Run: `make test`

Expected: 434 or more backend tests pass and the frontend production build completes successfully.

- [ ] **Step 5: Rebuild the runtime bundle and redeploy the workflow**

Follow the existing commands in `AGENT_STUDIO_3AGENT_SETUP.md`; verify the deployed artifact contains the updated OSSIE YAML, governance YAML, golden questions, and Agent Studio tool files before starting live tests.

- [ ] **Step 6: Run the live nine-domain acceptance matrix**

Execute one governed question for each of Sales, B2B, Stock Tempo, Stock SAT-IDM, SAT OOS, Service Level, Picking, Unloading, and SAT Promo. For Promo, repeat both safe questions twice through the REST API and once through the UI, then run the three refusal/period controls from Task 4.

Record trace ID, selected metric ID, source view, dimensions, caveat, final answer, latency, and PASS/FAIL in `docs/qa/2026-09-28-agent-studio-nine-domain-acceptance.md`. Never store the API key, Authorization header, or cookies.

- [ ] **Step 7: Run the final verification**

Run: `PYTHONPATH=backend .venv/bin/python scripts/validate_tempo_impala_contract.py --json && make test`

Expected: contract valid with 15 datasets/50 metrics; all tests and frontend build pass; live matrix has nine governed domains and zero unsafe Promo resolutions.

- [ ] **Step 8: Commit deployment guidance and acceptance evidence**

```bash
git add projects/tempo_scan_impala/agents/AGENT_STUDIO_3AGENT_SETUP.md projects/tempo_scan_impala/agent_studio_tools/AGENT_STUDIO_SETUP.md docs/qa/2026-09-28-agent-studio-nine-domain-acceptance.md backend/tests/test_tempo_agent_studio_tools.py
git commit -m "docs: validate nine-domain Agent Studio workflow"
```
