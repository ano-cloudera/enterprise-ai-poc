# Documentation index (Tempo Scan · enterprise-ai-poc)

**Last reviewed:** 7 Oct 2026  
**Source of truth for “where we are now”:** [`PROJECT_STATE.md`](../PROJECT_STATE.md), [`PROJECT_STATUS.md`](../PROJECT_STATUS.md)

---

## Use these first (active)

| Doc | Purpose |
|-----|---------|
| [`cloudera-ai-deployment.md`](cloudera-ai-deployment.md) | CAI split deploy (frontend + backend + Qwen), env vars, troubleshooting |
| [`cai-application-deployment-config.md`](cai-application-deployment-config.md) | Copy-paste Application config (Kerberos Impala, ports) |
| [`tempo-impala-ossie-runbook.md`](tempo-impala-ossie-runbook.md) | Impala + OSSIE governed mode, validation, rollback |
| [`data-enhancement-views.md`](data-enhancement-views.md) | Optional Gold views (B2B branch×material, promo B2B uplift, SL cust group) |
| [`architecture.md`](architecture.md) | LangGraph flow, contracts, guardrails (v2 baseline) |
| [`api-contract-v2.md`](api-contract-v2.md) | Chat response shape (`answer`, `data`, `chart_spec`, …) |
| [`semantic-layer.md`](semantic-layer.md) | OSSIE / governed semantic model (primary path) |
| [`nl-to-sql.md`](nl-to-sql.md) | Deterministic SQL path + OSSIE governed path |
| [`golden-questions.md`](golden-questions.md) | Executable golden suite location |
| [`qwen-integration.md`](qwen-integration.md) | Remote LLM boundary (post-query analysis only) |
| [`health.md`](health.md) | Health/readiness endpoints |
| [`impala-mapping.md`](impala-mapping.md) | Impala catalog / view mapping notes |
| [`dwh-migration-checklist.md`](dwh-migration-checklist.md) | On-prem cluster migration (historical ops, still useful for infra) |
| [`irvan-semantic-model-audit.md`](irvan-semantic-model-audit.md) | External semantic model comparison / PERLU VALIDASI views |
| [`ui-design-system.md`](ui-design-system.md) | Frontend tokens / layout conventions |

**Automated UAT (replaces manual `docs/uat-*` transcripts):**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python scripts/run_uat_domain_5x5_followup.py --yaml=uat_domain_3x1_mgmt_final.yaml
```

Merged results: `backend/eval/*_merged_latest.json`.

---

## Secondary (features still in repo, not primary demo path)

| Doc | When to read |
|-----|----------------|
| [`trino-demo-data.md`](trino-demo-data.md) | CDW Trino bootstrap / parity (optional vs Impala production) |
| [`forecasting.md`](forecasting.md) | Offline XGBoost forecast tool |
| [`weather-external-signal.md`](weather-external-signal.md) | Weather external signal PoC |
| [`market-intelligence.md`](market-intelligence.md) | Serper market snapshot PoC |
| [`SEMANTICA_ASSESSMENT.md`](SEMANTICA_ASSESSMENT.md) | Future Semantica evaluation only — no runtime dependency |

---

## Foundation v2 (accurate but high-level; update as needed)

| Doc | Status |
|-----|--------|
| [`repository-structure-v2.md`](repository-structure-v2.md) | **Updated** — includes `tempo_scan_impala`, `backend-test`, eval |
| [`development-sequence-v2.md`](development-sequence-v2.md) | Milestone order; core Ask AI steps 1–8 largely **done** |
| [`CHANGELOG-v2.md`](CHANGELOG-v2.md) | Milestone 1–2 snapshot — **historical** |

---

## Recommended to archive (not deleted yet)

These are **not** linked from root `README.md` as operator docs. They are audit/history or superseded by OSSIE + `backend/eval/`.

| Path | Verdict | Superseded by |
|------|---------|----------------|
| `handoff/` | Archive | `PROJECT_STATE.md` |
| `superpowers/` | Archive | Implemented code + PROJECT_STATE |
| `uat/` | Archive | `backend/eval/*.yaml` + judge harness |
| `qa/2026-09-28-agent-studio-nine-domain-acceptance.md` | Archive | Automated UAT; contract counts stale |
| `uat-questions-2026-09-29.md` | Archive | 5×5 / 1×2 / 3×1 YAML suites |
| `uat/2026-10-02-nine-questions-resolver-uat.md` | Archive | pytest + eval harness |
| `remaining-work.md` | Archive | Management UAT 30/30, OSSIE live |
| `cai-deployment.md` | Archive | `cloudera-ai-deployment.md` |
| `diagrams/tempo-agent-studio-workflow.*` | Keep or archive | Agent Studio optional path |

**Partial archive already started:** `archive/handoff/` (duplicate of top-level `handoff/` — consolidate to one location when cleaning).

Suggested one-time cleanup (after you confirm):

```bash
cd docs
mkdir -p archive
git mv handoff superpowers uat qa archive/
git mv uat-questions-2026-09-29.md remaining-work.md CHANGELOG-v2.md cai-deployment.md archive/
```

---

## Out of scope for `docs/` cleanup

- `backend/docs/PHASE_C_ROADMAP.md` — backend implementation notes  
- `backend-v2/docs/` — legacy tree; do not treat as current product  
- `projects/tempo_scan_impala/` — live OSSIE YAML (not under `docs/`)
