# Tempo Scan Commercial Intelligence — Project State

**Repo**: `enterprise-ai-poc` (github.com/ano-cloudera/enterprise-ai-poc), branch `main`
**Updated**: 9 Oct 2026 (PM) — **Analysis Workspace (Genie-style) merged to production** (`a213b52`, pushed `origin/main`). **Production FE** (`frontend/`): split-pane **Analysis Workspace** beside chat — tabs **Summary | Table | Query**, draggable split (`useReportSplitPane.ts`, `AnalysisSplitHandle.tsx`), artifact card opens panel (`ReportArtifactCard.tsx`); Summary sections use shared typography (`workspace-section-title` / `workspace-body-text` in `index.css`); workspace charts **+15% height**, duplicate chart title suppressed (`AnswerChart` `hideTitle`); Query tab shows **SQL + data note + Source only** (removed Read-only/Impala/ms/rows chips and METRIC pill block). **Production BE**: `AskDataResponse.governed_sql` populated from validated SQL in `chat.py` for Query tab. **Pilot trees in git**: `frontend-dev/` + `backend-dev/` (same UX/features for isolated iteration); **`scripts/run-dev-stack.sh`** → http://127.0.0.1:3001 + :8001, Ingram Impala preflight. **Docs**: `docs/analysis-report-dev.md`, `docs/reusable-fe-capabilities.md`. **Do not commit**: local PDF exports under `frontend/` / `frontend-dev/`; `*_hardcoded*.py` Workbench scripts (gitignored). **Port clash**: `backend-test/` and `run-dev-stack.sh` both target **8001** — run one at a time. **Same-day earlier**: Neo4j ontology mirror (optional), matrix routing & narrative chart suppress, Usage tab — sections below unchanged in substance.

## Current checkpoint: Analysis Workspace in production (9 Oct 2026, PM)

### Shipped (commit `a213b52`)

| Area | Paths / notes |
|------|----------------|
| Panel shell | `frontend/src/components/AnalysisReportPanel.tsx`, `AskDataPage.tsx`, `AppShell.tsx` |
| Document body | `ReportDocumentSection.tsx`, `analysis/Workspace*.tsx`, `analysis/CollapsibleDataNote.tsx` |
| Chat entry | `ReportArtifactCard.tsx`, `lib/reportDocument.ts` |
| Split resize | `AnalysisSplitHandle.tsx`, `lib/useReportSplitPane.ts`, CSS `split-pane-*` + `scrollbar-pane` |
| Table tab | `WorkspaceDataTable.tsx`, `lib/workspaceTableLabels.ts`, `lib/exportTableCsv.ts` |
| Query tab | `WorkspaceQueryView.tsx` — governed SQL copy/wrap; lineage link if `NEXT_PUBLIC_LINEAGE_VIEW_URL` set |
| Config | `appConfig.ts`: `analysisReportPanel`, `reportDocumentLabel`, `viewLineageBaseUrl`, … |
| API | `frontend/src/types/api.ts` + `backend/app/core/models.py` → `governed_sql` |

**Verify prod UI:** `make dev` → ask a governed question with chart/table → artifact card → panel Summary/Table/Query. **`npm run build`** in `frontend/` was green after merge.

### Run modes (handoff)

| Mode | Command | UI | API |
|------|---------|-----|-----|
| **Production** | `make dev` | :3000 | :8000 |
| **Pilot stack** | `./scripts/run-dev-stack.sh` | :3001 | :8001 (`backend-dev`) |
| **DuckDB sandbox** | `backend-test/start.sh` | (point FE env) | :8001 — **conflicts with pilot** |

Pilot stack: repo `.env`, `IMPALA_CREDENTIAL_PROFILE=ingram` (override `DEV_IMPALA_PROFILE`), Kerberos `kinit` as needed; `DEV_SKIP_IMPALA_SMOKE=1` for UI-only.

### Feature flags (frontend)

| Env | Default | Meaning |
|-----|---------|---------|
| `NEXT_PUBLIC_ANALYSIS_REPORT_PANEL` | `true` | Set `false` to disable split workspace |
| `NEXT_PUBLIC_LINEAGE_VIEW_URL` | empty | Optional base URL for “View lineage” on Query sources |
| `NEXT_PUBLIC_REPORT_DOCUMENT_LABEL` | `Analysis Workspace` | Panel breadcrumb label |

### Not done / optional next

- Wire **`docs/slides/`** (untracked HTML deck) if management wants updated screenshots.
- **`backend-dev` vs `backend/`**: routing/UAT fixes should usually land in `backend/` first; dev tree is a mirror for faster FE iteration — re-sync or cherry-pick when diverging.
- Streaming TTFT / partial SSE (table before analyst) still not implemented — latency ~40–60 s unchanged.

## Previous checkpoint: demo-ready Ask AI + history follow-ups (9 Oct 2026, AM)

### Neo4j business ontology mirror (9 Oct)

- **Source of truth**: `backend/knowledge/tempo_domain_graph.yaml` (git); Neo4j is optional runtime mirror for `IntentRule` / clarify nodes.
- **Backend**: `neo4j_client.py`, config `NEO4J_*`; `domain_graph.governed_intents_for_routing()` / `clarification_intents_for_routing()` prefer Neo4j when enabled + ping OK.
- **Local**: `docker-compose.neo4j.yml`, `bash scripts/run-neo4j-local.sh`, seed with `cd backend && python scripts/seed_neo4j_domain_graph.py --clear`.
- **CAI**: separate **Tempo Scan Neo4j Ontology** application (seed/health only; FE never talks to Bolt). Linked from `docs/cloudera-ai-deployment.md`.

### Matrix routing & sell-through follow-ups (9 Oct)

- **`semantic/context.py`**: dual-metric clarification evaluated even during `continue_session` / `explain_prior`; bill-to-PO resolution skipped when question names both PO ratio and gross billing ranking.
- **`tempo_domain_graph.yaml`**: `cabang_kontribusi_sell_in_rank`, expanded billing clarify terms, documented `follow_up_intents` for DC top produk laku.
- **`follow_up.py`**: `_wants_sell_out_product_drill`, DC city catalog bind + fuzzy typo (e.g. “pelembang” → Palembang).
- **Regression script**: `scripts/smoke_session_regressions_oct2026.py` (multi-turn scenarios for manual/live smoke).

### Narrative-first answers (9 Oct)

- **`should_suppress_chart_for_narrative`**: deep analisa / kenapa / saran perbaikan without explicit chart request → workflow clears `chart_spec` after analyst pass.
- **Prompt**: `result_analyst.md` instructs null chart for narrative-only asks.

### LLM Usage monitoring (8 Oct, PM)

- **Backend**: `usage_store.py` (SQLite), `usage_context.py` + `UsageTracker` keyed by `request_id`; providers record OpenAI-compatible / Gemini `usage_metadata`; `chat.py` attach on SSE `done`; config `USAGE_DB_PATH`, `USAGE_MONTHLY_TOKEN_BUDGET`.
- **API**: `app/api/usage.py` — summary, events, CSV export.
- **Frontend**: `UsagePage`, route `/usage`, `formatCompactTokens`, `formatUsageTimestampWib`; nav gated by `NEXT_PUBLIC_NAV_USAGE`.
- **Verify**: new Ask Data turn after backend reload; Usage empty for turns before fix (no backfill).

### Cross-domain entity time-series follow-ups (8 Oct, PM)

- **`follow_up.py`**: `_plan_filtered_entity_time_breakdown` — material, branch, sales_office (unloading → `reporting_period`), DC SAT, etc.; blocks monthly questions from re-running top-N material drill.
- **Tests**: `test_plan_follow_up_top_material_monthly_sell_in`, branch monthly, unloading `reporting_period`.

### Frontend shell (Scan Intelligence PoC, 8 Oct)

- **`appConfig` / `BrandMark` / `AppShell`**: white-label titles, collapsed rail icons, Usage link.
- **Usage chart**: `maxBarSize={48}` on daily bar chart.

### Governed SQL & bill-to-PO routing (7–8 Oct)

- **`stock_tempo_to_sell_in_ratio`** (`compile_governed`): `HAVING SUM(sell_in_bill_qty) > 0` and `ORDER BY … NULLS LAST` so top-N rankings are not dominated by NULL/zero sell-in; zero-movement intent skips the HAVING.
- **Bill-to-PO** business meaning = **`material_fill_rate`** on `gold.rpt_sap_material_month_semantic` (`service_do_qty` / `service_po_qty`), with contextual `service_po_qty`, `service_do_qty`, and **`sell_in_bill_val` only when the question asks billing value** — not `material_sell_in_value` / `sales_office_material_360`.
- **Routing** (`semantic/context.py`): `_bill_to_po_resolution()` runs **before** Pareto contribution and domain-graph governed intents; “proses penagihan” in analysis text no longer hijacks bill-to-PO questions. **`tempo_domain_graph.yaml`**: `bill_to_po_material_fill_rate` governed intent; dual-metric clarification only when explicit billing-value phrases appear (e.g. “nilai penagihan grosir”), with `unless_terms` for clear ranking questions.
- **8 Oct SQL polish**: “rasio positif” → `HAVING` on ratio > 0; “10 material” → `LIMIT 10`; penagihan-process wording without billing-value intent → ratio columns only (avoids ~7B IDR `sell_in_bill_val` dominating chart/narrative).
- **Tests**: `test_semantic_context.py` (`test_bill_to_po_positive_ratio_having_and_limit_ten_material`, bill-to-PO + long management-style prompt, clarification when both PO fulfillment and gross billing are named).

### Response latency & architecture (8 Oct)

- **Why ~40–60 s**: sequential LangGraph — understand (often skip) → governed compile → Impala → optional pareto enrichment → **`analyze_result`** structured LLM (~1800 tokens) → **`judge_answer`** (disabled fast-path when question includes analisa/rekomendasi; may **`retry_synthesize`**).
- **Per-request breakdown**: API `timings` (`query_ms`, `analysis_ms`, `total_ms`) and UI “View process” / backend log `ask_data … timings=…`.
- **Not a bug for PoC**: design targets governed SQL + structured `answer + data + chart_spec`; UI streams **stage labels**, not analyst tokens. Faster “feels like chat” would need partial SSE (table/chart after query) and/or ranking fast-path without full analyst — see team notes in chat (8 Oct 2026).
- **Demo tip**: data-first questions (top-N, bandingkan) per turn; deep “analisa + saran” on follow-up or accept longer waits; optional `JUDGE_ENABLED=false` in dev to drop retry synthesize.

### Ingram Gold audit & Kerberos (8 Oct)

- **Runbook**: `docs/ingram-gold-audit.md` — CAI `GSSError` checklist, OSSIE 24-source audit commands, view sync notes.
- **Scripts**: `scripts/audit_gold_ingram.py`, `scripts/validate_ingram_gold_views.py`; smoke **`backend/scripts/test_impala_ingram_env.py`** (loads `IMPALA_CREDENTIAL_PROFILE=ingram` from repo `.env`).
- **Do not commit**: `*_hardcoded.py` Workbench helpers with embedded passwords; sample audit SQL under `datasets/audit/` is OK.

- **DC penumpukan / stok partner:** `_dc_partner_stock_penumpukan_resolution()` runs early (before Pareto sell-in and generic “penagihan”). Routes **DC + penumpukan/stok** → `sat_dc_stock_quantity` (default) or `sat_dc_stock_value` when nilai/rupiah explicit @ **`dcname`** (`rpt_sat_dc_month`), not `material_sell_in_value`. Domain graph `dc_stock_penumpukan_rank` aligned to quantity; analyst prompt labels `dcname` as SAT partner stock vs `sales_office` / `branch`. See `backend/knowledge/README.md` routing guardrails.

### Cross-domain & multi-turn (7 Oct)

- **`cross_domain_compare.py`**: maps paired domains (sell-in+B2B, stock Tempo+sell-in, DC SAT+sell-out, etc.) to published OSSIE journey metrics; wired in `semantic/context.py` (**evaluated before `session_analysis_context` follow-up**, then multi-concept fallback) and `follow_up.py` (entity from ranking → e.g. material sell-in vs B2B ratio).
- **Tempo recording script**: `eval/uat_tempo_demo_record_oct2026.yaml` — Batch 1 (12-turn journey), Batch 2 (10 management), Batch 3 (10× follow-up); dry-run 42/42 resolver; live Batch 1 **12/12**, Batch 2 **10/10** (Oct 2026).
- **Tests**: `tests/test_cross_domain_compare.py`, extended `test_follow_up_p0_scenarios.py` (sell-in top material → B2B sameness).
- **Manual scripts**: see chat in repo history — e.g. top sell-in → *“material itu, bandingkan sell-in vs B2B”*; single-turn *“big picture sell-in vs sell-out Q4”*.
- **Not yet**: one message → multiple independent governed queries with merged wide table (backend compose); still **one metric/query per turn**.

### History-only follow-up (7 Oct, PM)

- **`try_history_only_analysis_resolution`** in `follow_up.py`: “kenapa … dibanding yang lain” reuses prior turn rows → LangGraph skips `execute_query` → `result_analyst_history_only.md`.
- **Routing fixes**: `dibanding` ≠ governed compare; explicit top-N after pareto; `Strategy` includes `history_only_analysis` for API/PDF meta.
- **UAT**: `eval/uat_demo_management_journey.yaml`, `eval/uat_demo_pareto_then_top10.yaml` — run via `run_uat_domain_5x5_followup.py --yaml=…`.

### Frontend & docs (7 Oct)

- **PDF**: `frontend/src/lib/chatPdfExport.ts` — structured A4 (ID section labels, turn dividers, chart height cap, meta strip, `jspdf-autotable`), chart snapshot via `data-pdf-export-chart`.
- **Settings**: draft model + **Save model** → Redux + `localStorage` key `tempo-scan-v2.model-selection` (no backend profile API).
- **UI**: user message bubble max width ~78% / 28rem; `docs/architecture-highlevel.md` + Mermaid sources and PNG exports.

## Previous checkpoint: production-ready governed stack + UAT sign-off (7 Oct 2026)

### UAT harness (Gemini judge + mechanical checks, backend on `:8000`)

| Suite | YAML | Merged result (committed) |
|-------|------|---------------------------|
| 5×2 follow-up | `uat_domain_5x5_followup.yaml` | **50/50** `uat_domain_5x5_followup_merged_latest.json` |
| 1×2 smoke / domain | `uat_domain_1x2_followup.yaml` | **10/10** `uat_domain_1x2_followup_merged_latest.json` |
| 3×1 management (ID) | `uat_domain_3x1_mgmt_final.yaml` | **30/30** `uat_domain_3x1_mgmt_final_merged_latest.json` |

Run: `cd backend && PYTHONPATH=. ../.venv/bin/python scripts/run_uat_domain_5x5_followup.py --yaml=<file>` · merge: `scripts/merge_uat_followup_reports.py`.

### OSSIE + Impala enhancements

- **Gold views** (optional deploy): `gold.corr_b2b_branch_material_month`, `gold.rpt_sat_promo_b2b_sellout_uplift`, `gold.corr_service_sales_office_cust_group_material_month` — `docs/data-enhancement-views.md`, deploy helper `scripts/deploy_gold_enhancement_views.py`.
- **New governed objects**: `b2b_branch_material_*`, `promo_b2b_sellout_*`, `sales_office_cust_group_service_fill_rate`; B2B branch×material follow-up; promo B2B uplift routing; stock-cover SQL fixes; deterministic ops/unloading workload narrative when analyst LLM flakes.

### Local run

- **Governed Ask AI**: `make dev` → UI http://127.0.0.1:3000 , API http://127.0.0.1:8000 (`frontend/.env.local` → `BACKEND_API_URL=8000`).
- **Exploratory DuckDB**: `backend-test/start.sh` → **8001** (change FE env if switching modes).

### Documentation (7 Oct)

- **Index:** `docs/README.md` — active operator docs vs recommended archive (`handoff/`, `superpowers/`, `uat/`, manual UAT lists).
- **Updated:** `semantic-layer.md`, `golden-questions.md`, `tempo-impala-ossie-runbook.md`, `repository-structure-v2.md`, OSSIE notes in `architecture.md` / `nl-to-sql.md`.
- **Archive:** `docs/archive/` holds `handoff/`, `superpowers/`, `uat/`, `qa/`, and legacy checklists; index at `docs/README.md`.
- **Removed:** Gradio harness (`gradio-test/`, `testing/model/gradio/`) — UI = `frontend/` only.

### Frontend (7 Oct, earlier)

- Evidence block: embedded Recharts height/margins + `-mt-2` table toggle so chart and **Hide table detail** sit closer (management demo layout).

## Previous checkpoint: follow-up UAT P0 + OSSIE multi-turn stack (6 Oct 2026)

### Goal

50 follow-up scenarios (5 per domain × 10 domains, 2 turns each, shared `session_id`) scored by **Gemini management judge** plus mechanical HTTP checks. Baseline before this work was ~25/50 scenarios on judge; mechanical-only merge reached ~40/50 before judge strictness.

### What landed (backend)

- **Follow-up pipeline**: `app/services/follow_up.py` (heuristic plan before LLM), `session_context.py` (referential rewrite, rank/compare, plant/material drill), `question_contextualize.py`, `chat.py` turn understanding (lite/clarify/follow_up).
- **Governed path**: `semantic/context.py` (session metric continuation, extra predicates, OOS worst-first), `graph/workflow.py` (follow-up catalog row fallback, synthetic entity rows, skip false NO_DATA on follow-up context).
- **Conversational**: `conversational.py` for sell-in vs sell-out concept questions (cross-domain UAT).
- **Phase C**: judge replan (`judge.py`, `governed_replan.py`), domain graph (`knowledge/tempo_domain_graph.yaml`), OSSIE trace, ask-data routing, eval harness (`eval/uat_answer_judge.py`, `scripts/run_uat_domain_5x5_followup.py`, merge script, `eval/uat_domain_5x5_followup.yaml`).
- **Frontend-v2**: streaming progress, session list, answer prose/PDF, RTK store, clarification UX aligned with backend `session_frame`.

### UAT status (6 Oct 2026, merged best-of per domain)

| Domain | Scenarios pass (latest merge) |
|--------|-------------------------------|
| All 10 domains (stock_sat, b2b, cross_domain, picking, sat_oos, stock_tempo, unloading, sales, service_level, promo) | **5/5** each |

**Totals**: **50/50** scenarios in merged JSON (`eval/uat_domain_5x5_followup_merged_latest.json`). Re-run per domain: `scripts/run_uat_domain_5x5_followup.py --domain=<id>` then merge.

Run: `backend/scripts/run_uat_domain_5x5_followup_all_domains.sh` (one process per domain; restart backend after code changes). Ephemeral per-run JSON is gitignored; committed summary: `eval/uat_domain_5x5_followup_merged_latest.json`.

### P1 follow-up (post 50/50)

- Maintain merged JSON when adding scenarios; watch analyst narrative drift on edge follow-ups (picking, stock_tempo) even when mechanical + judge pass.
- Optional: full-domain regression script before releases (`run_uat_domain_5x5_followup_all_domains.sh`).

### Tests

New follow-up/judge/routing tests under `backend/tests/test_follow_up*.py`, `test_session_context.py`, etc. Full `pytest backend/tests`: **270/270** (Oct 2026) — tests aligned with Phase C (semantic `unsupported` → clarification, readiness component fields, env-isolated `isolated_settings()` helper).

### Ops

- Local stack: `scripts/run-local-stack-governed.sh` or `run-local-stack-ossie-only.sh`.
- UAT latency ~30–60 s/turn governed (+ judge; analisa/saran often upper band); frontend stream abort default **180 s** (Ask Data).

## Previous checkpoint: UAT cabang fill-rate ranking uses governed sales-office view (2 Oct 2026)

Live UAT still showed `company_fill_rate` (~77.7%) with text claiming no cabang dimension — that symptom matches **pre-fix** resolver behavior on the deployed CAI app (shortcut knew `fill rate` but not `cabang` as sales-office grain). The gold view and metric already existed (`sales_office_service_fill_rate` → `gold.corr_service_sales_office_material_month`); Irvan’s Local Agent also covers this, but the main Ask Data path should not depend on fallback when OSSIE already publishes the breakdown.

Fix (minimal, resolver + compile only): (1) treat `cabang`/`branch` like `sales office` in the fill-rate / service-level shortcut; (2) treat `service level` phrasing the same as `fill rate` when routing that shortcut; (3) add `terjelek` (and `urutkan` as ranking intent) so `compile_governed()` sorts worst-first (`ORDER BY metric_value ASC`) instead of default DESC. End-to-end workflow test confirms `strategy=governed`, SQL hits `corr_service_sales_office_material_month`, and the LLM planner is not used for planning. TEMPO Local Agent remains available for genuinely unsupported questions via `LOCAL_AGENT_BASE_URL` — not required for this UAT sentence once redeployed.

Regression: UAT sentence + two nearby branch-ranking phrasings; full `backend/tests/` **145/145**. All **82** golden questions unchanged / zero compile errors. Redeploy backend on CAI required for the live UI to change; env-only Local Agent without this resolver fix would still show the old company aggregate.

## Previous checkpoint: false-positive clarification/dimension-mismatch bugs found via live UAT, UI/UX polish (2 Oct 2026)

### Context: live-testing the 9-question list plus everything enriched this session

After the previous two checkpoints' domain enrichment and gap-closing work, the user ran the original 9-question PDF list end-to-end against the live UI (not just `resolve()`/`compile_governed()` in isolation) to sanity-check everything together, including the ROI-promo proxy clarification flow. This surfaced two real bugs invisible to isolated unit testing - both are "brand name / common word causes a false match" bugs, same root-cause family as the "di tempo" discriminator problem described below.

### Bug 1: `contextualize_question()` swallowed an unrelated new question into a stale clarification

Asking "Hitung promo dengan ROI terbaik..." correctly produced the ROI-promo-proxy clarification (3 metric options, by design - no direct ROI metric exists). But the very next, completely unrelated question - "Top 10 produk dengan penjualan terbesar di Tempo" - got silently rewritten by `contextualize_question()` (`app/services/chat.py`) into "`<old ROI question>`\nKlarifikasi pengguna: Top 10 produk...", because the two texts shared the single common word "penjualan" or "tempo" (the brand name, present in nearly every question). The function's token-overlap heuristic only required **one** shared token to treat a new question as a clarification answer. Fixed: `"tempo"` added to the ignored filler-word set, and at least **two** overlapping tokens (or an exact canonical match) are now required. Verified against all existing `test_history.py`/`test_semantic_context.py` clarification-matching tests - all still pass (the legitimate short-reply cases like "stok retail" share 2+ specific tokens with their clarification, so the stricter threshold doesn't affect them).

### Bug 2: the `sales_stage` ambiguity's "di tempo" discriminator auto-selected Sell-In for almost any question

Root cause of the ROI-promo clarification not even being reached correctly in some phrasings: `tempo_governance.yaml`'s `sales_stage` ambiguity had a bare `"di tempo"` discriminator for the Sell-In option - since the brand name appears in nearly every Sell-In-flavored question, this silently auto-selected Sell-In and skipped the Sell-In/Sell-Out clarification entirely for genuinely ambiguous questions (e.g. "penjualan terbesar di Tempo"). This is a **pre-existing bug from the feature's original commit**, not introduced this session. Removed the discriminator; genuinely Sell-In questions still have stronger signals (`sell-in`, `gross sales`, `tempo ke customer`, `general trade`) unaffected by the removal.

### Bug 3 (found while live-testing question #2 of the 9-question list): false `dimension_mismatch` for the ambiguous word "cabang"

"Top 10 cabang/ sales office dengan penjualan terbesar di tempo" returned a hard `ERROR` in the live UI ("Query data tidak dapat diselesaikan"). Root cause: the Indonesian word "cabang" hints three different dimension names at once in `registry.py`'s `dimension_terms` (`branch` for B2B partner branch, `sales_off` and `sales_office` - two physically different column names across different gold views for the same Tempo-sales-office concept). `resolve_metric()`'s `dimension_mismatch = hinted_dimensions - {calmonth} - allowed_dimensions` treated each hinted name independently, so even when the winning metric (`sales_office_material_sell_in_value`, `allowed_dimensions` includes `sales_office`) genuinely covered one reading of "cabang", the other two synonym names (`branch`, `sales_off`) were still reported as unmet. A non-empty `dimension_mismatch` makes `plan_query()` (`app/graph/workflow.py`) skip the already-correct governed SQL and hand the question to the LLM fallback planner instead - which then produced invalid SQL and surfaced as the live `ERROR`.

Fixed: once any member of the `{branch, sales_off, sales_office}` synonym group is actually covered by the winning metric's `allowed_dimensions`, the other members are dropped from `hinted_dimensions` before computing the mismatch - they were never separate unanswered requests, just alternate readings of the one "cabang" the question asked for. Live-verified: the question now compiles to governed SQL and returns the correct per-sales-office ranking (sales office `0201` leading at Rp356.27M).

**Verified against all 82 `golden_questions.yaml` questions before/after this fix**: 8 questions improved (false `dimension_mismatch` went from non-empty to `[]`, also affecting several Picking/Unloading-domain questions that share the same "cabang"/"sales office" ambiguity), zero regressions.

### UI/UX polish (separate from the resolver bugs above, done earlier in this session)

- **Chart/table duplication**: the result analyst's `insights` field was restating every row already visible in the chart/table as prose bullets. `prompts/result_analyst.md` now explicitly forbids repeating chart/table rows in `insights` - only genuine observations (patterns, outliers, gaps, caveats) belong there. Frontend (`frontend/src/views/AskDataPage.tsx`): the data table now collapses by default (with a "Show/Hide table detail" toggle) whenever a visual chart (bar/line/area/scatter/pie) already renders the same rows; KPI-only or chart-less responses keep the table expanded as before.
- **Font-size consistency**: replaced scattered arbitrary `text-[Npx]` values across the chat flow (user bubble, AI answer body, KPI card, SQL block, footer) with the standard Tailwind scale (`text-xs`/`text-sm`/`text-base`/`text-2xl`) so proportions stay consistent when zooming.
- **Header badge**: replaced the top header's "Governed Ossie + Impala" chip with a green-dot "Database" indicator, matching the chat panel's existing badge style.

### Tests

6 new regression tests added this checkpoint (3 for the clarification/discriminator bugs in `tests/test_history.py`/`tests/test_semantic_context.py`, 3 for the `dimension_mismatch` synonym-group fix). Full suite: **140/140 passing** (134 from the prior checkpoint + 6 new). Frontend: 15/15 passing (unchanged by this checkpoint's UI work, verified after each change).

### Not yet done

- The `dimension_mismatch` synonym-group fix only covers the `branch`/`sales_off`/`sales_office` group (the one concretely found broken). If other dimension names end up with the same multi-hint-from-one-Indonesian-word pattern in future domain work, the same symptom (false mismatch forcing LLM fallback) could recur elsewhere - worth a broader audit if another live-UAT failure surfaces a similar case.
- Fill-rate/OOS/stock-cover `resolve()` shortcuts' `dimensions=[]`/non-empty-list convention still blocks trend-prepend for a few metrics (`material_fill_rate` with `dimensions=["material"]`) - flagged in the prior checkpoint, still not fixed, needs a dedicated pass.

## Previous checkpoint: trend shortcut fix, zero-movement product metric, OOS per-store breakdown (2 Oct 2026)

### Context: closing the 3 remaining "orange" items from the 9-domain enrichment checklist

After the previous checkpoint's domain enrichment pass, 3 items remained flagged "orange" (known gap, not yet fixed): (1) trend/"per bulan" questions not working for several metrics that route through `resolve()`'s dimensionless shortcuts, (2) no way to ask "produk mana yang tidak laku sama sekali" (zero-movement products), (3) SAT OOS questions naming a store/outlet/gerai not actually breaking down by store. Confirmed all 3 needed **no new Impala view** — the underlying gold views already have the needed columns; these were purely semantic-layer (`context.py`) gaps.

### 1. Trend shortcut fix: empty `dimensions=[]` was blocking the trend-prepend logic

`resolve()`'s `resolved()` helper (used by `company_fill_rate`, `sat_oos_rate`, `material_fill_rate`, `months_of_stock_cover`, `service_unfulfilled_quantity`, etc.) always passes an explicit `dimensions` list into `compile_governed()` — including `[]` for its default company-wide grain. `compile_governed()`'s trend-prepend guard only fired when `requested_dimensions is None`, so `[]` (meant as "no explicit choice yet", not "user explicitly wants zero dimensions") silently skipped trend detection entirely — "tren fill rate per bulan" never got a `GROUP BY calmonth`. Fixed: the guard now also fires for `requested_dimensions == []`, while any genuinely non-empty explicit list (e.g. `["material"]` from `material_fill_rate`) is left untouched, so shortcuts that deliberately picked a non-time grain aren't second-guessed. Verified live and via `compile_governed()`: `"tren fill rate per bulan"`, `"tren SAT OOS per bulan"`, `"tren stok cover per bulan"` now all produce `GROUP BY` + chronological `ORDER BY ... ASC` (from the prior checkpoint's trend-ordering fix); non-trend shortcut questions (`"fill rate kita sekarang berapa"`) remain unaffected (still dimensionless).

### 2. New capability: "produk tidak laku" / zero-movement products via governed `HAVING`

Confirmed live that the data genuinely supports this question: 22,852 of 25,125 materials in `gold.rpt_sap_material_month_semantic` have `sell_in_bill_val = 0` across Q4 2024. Added a new `requests_zero_movement` detector in `compile_governed()` (keywords: "tidak laku", "zero movement", "tidak terjual", "tidak ada penjualan", etc.) that appends a `HAVING` clause after `GROUP BY`. **Impala-specific gotcha found and fixed during live verification**: Impala cannot resolve a `SELECT`-aliased column (`metric_value`) inside `HAVING` (`AnalysisException: Could not resolve column/field reference: 'metric_value'`) — the fix repeats the actual aggregate expression (`HAVING SUM(d.sell_in_bill_val) = 0`) instead of the alias. Live-verified: query returns 50/50 rows all with `metric_value = 0.0`. Added matching Indonesian aliases to `material_sell_in_value`/`material_sell_out_value` in `tempo_core.ossie.yaml`; confirmed no collision with the existing "paling laku"/"terlaris" (best-seller) aliases, which correctly do not trigger the `HAVING` clause.

### 3. SAT OOS: store/outlet/gerai breakdown, with a deliberate aggregate-vs-ranking distinction

`sat_oos_rate`'s `allowed_dimensions` already included `cust_id`/`cust_code`, but the `mentions_oos` dimension-selection block in `context.py` only recognized "customer"/"pelanggan" for that breakdown — "toko mana yang paling sering OOS" resolved to the right metric but with `dimensions=[]` (a single aggregate number, no per-store breakdown at all). Also added "kehabisan" + "stok"/"stock" as a `mentions_oos` trigger (previously only "kosong" was recognized, inconsistent with the OOS-skip language already added to `registry.py`'s ambiguity-skip in the previous checkpoint), and added "produk"/"sku" alongside "material" for the material-side breakdown.

**Regression caught and fixed during testing**: naively adding bare "toko"/"outlet"/"gerai" to the breakdown trigger broke an existing test (`test_natural_sat_oos_questions_route_to_oos_metric`) — "Berapa persen toko yang kosong stoknya pas disurvei bulan lalu?" is an aggregate question ("what percent of stores"), not a per-store ranking, and was wrongly forced into a `cust_id`/`cust_code` breakdown. Fixed by gating the store breakdown on store language *plus* an explicit ranking signal (`mana`, `tertinggi`, `terbesar`, `terendah`, `terkecil`, `terparah`, `terburuk`) — "toko mana"/"outlet dengan OOS tertinggi" now correctly break down by store, while "berapa persen toko" correctly stays a single aggregate. Live-verified the per-store query against Impala (real OOS rates, up to 100% for the worst stores in the ranking).

### Tests

11 new regression tests added to `tests/test_semantic_context.py`: trend-via-shortcut `GROUP BY`+chronological order (3 questions), non-trend shortcut stays dimensionless, zero-movement `HAVING` clause present, best-seller questions do NOT trigger `HAVING` (2 questions), OOS store-ranking breakdown (3 questions), OOS aggregate-percentage question stays dimensionless. Full suite: **132/132 passing** (121 baseline + 11 new). Metric count assertion unchanged at 66 (no new metrics, only logic + aliases).

### Not yet done

- `"tren fill rate material per bulan"` (→ `material_fill_rate`, `dimensions=["material"]`, a genuinely non-empty explicit list) still does not get a calmonth breakdown added on top of material — deliberately left out of this fix's scope (the `== []` guard is conservative by design); would need a separate, explicitly-scoped decision about whether non-empty shortcut dimension lists should also allow trend-append.
- Zero-movement detection only applies to `material_sell_in_value`/`material_sell_out_value` so far; the same `HAVING` mechanism in `compile_governed()` is generic (works for any metric+dimension combination), so extending it to other "underperforming X" questions (e.g. zero-movement outlets) is just an aliasing exercise, not new plumbing.

## Previous checkpoint: domain enrichment (governed dimensions + Indonesian aliases), outlet ambiguity fix, trend ORDER BY fix (2 Oct 2026)

### Context: continuing from the 1 Oct dry-run audit, now broadening beyond the original 9 PDF questions

The dry-run audit (previous checkpoint, below) fixed the 9 specific PDF questions. This session's explicit goal, per the user, was broader: enrich question-answering potential across *every* domain/dataset/Impala view, not just the 9 original questions — and account for how varied/colloquial real Indonesian phrasing is ("orang indonesia itu bahasa nya kaya dan beragam"). User explicitly authorized creating new Impala views/metrics where the underlying data supports it, with human-readable descriptions.

### Clarification-answer-lost bug fixed first

`_canonical_clarification_choice()` in `app/services/chat.py` required exact-set membership (`normalized in {"sell in", ...}`) with no tolerance for filler words, and its fallback token-check failed because "sell-out" (dashed, one token in the AI's own question text) never matched "sell"+"out" (two separate tokens in the user's undashed reply). A reply like "untuk sell out" was silently dropped, causing the AI to lose context and ask a second, wrong clarification. Fixed to substring matching (`any(phrase in normalized for phrase in sell_in_phrases/sell_out_phrases)`); verified via direct calls and `SemanticContextService.resolve()`/`compile_governed()` producing correct SQL. Full suite green throughout.

### Domain-by-domain enrichment: newly-activated governed dimensions

A gap analysis (comparing every dataset's declared fields in `tempo_core.ossie.yaml` against which fields actually appear inside some metric's SQL expression) found several fields that existed in the Gold views but were never exposed as queryable breakdowns. Activated:

- **Stock Tempo**: `plant` (gudang) breakdown for `stock_tempo_total_qty`/`stock_tempo_value` — "mana"-style ranking phrasings ("stok gudang Tempo mana yang paling banyak") previously lost to the wrong, plant-less metric (`material_warehouse_stock_quantity`) purely on alias-substring-length scoring; fixed with longer, exact-word-order aliases that win the scoring race, plus live-verified `GROUP BY plant` SQL.
- **Stock Tempo**: new metric `stock_tempo_consignment_qty` (previously-unused `consignment_stock_qty` field, confirmed live: 1.28M units across ~6% of rows, real plant-level breakdown e.g. plant 2300 leading at 550,855 units) — metric count assertion in `tests/test_semantic_context.py` bumped 65→66.
- **SAT stock (DC/store)**: `division` (unit bisnis / BCL/FOOD/MILK/OTC) breakdown added to all 4 SAT stock metrics (`sat_dc_stock_quantity/value`, `sat_store_stock_quantity/value`), plus a `division`/`divisi`/`unit bisnis` hint in `context.py`'s `compile_governed()`.
- **Service Level**: `fill_rate_band` breakdown — required a new explicit intent branch in `context.py` (`mentions_fill_rate_band`) since the pre-existing deterministic fill-rate routing block intercepted "per band"/"kategori fill rate" questions before alias scoring ever got a chance to pick a band-aware metric.
- **SAT Promo**: `mekanisme`/`program_status` breakdown activated on `promo_observation_count`/`promo_material_count`, with hints added to `context.py` and matching Indonesian aliases ("mekanisme promo apa yang paling banyak", "jumlah observasi per status program").
- **Cross-domain reconciliation**: confirmed `reconciliation_scope` is a constant (`shared_customer_only`, 100% of rows) — not a real breakdown gap, correctly left alone. Instead enriched the genuinely useful axis (`customer`) on `sell_in_minus_sell_out_value`/`sell_out_to_sell_in_value_ratio`, and fixed the `sales_stage` ambiguity wrongly intercepting ratio/gap-phrased reconciliation questions before the more-specific `ratio_direction` ambiguity could run (added a `rasio`/`ratio`/`selisih`/`gap`/`variance`-based skip in `registry.py`'s `resolve_ambiguity()`, plus new `trigger_terms`/discriminators on `ratio_direction` in `tempo_governance.yaml`).
- **SAT OOS**: added colloquial "kehabisan"/"kosong" phrasings with a matching `stock_scope` ambiguity-skip (same pattern as the pre-existing OOS/consignment skips).
- Broad additional Indonesian synonym coverage added to `gross_billing_value`, `material_sell_out_value`, and the existing (already correctly row-weighted) picking/unloading duration metrics — caught and reverted an accidental metric-duplication mistake along the way (don't re-declare a metric that already exists with a better, row-weighted expression; check existing `- name:` blocks first).

### B2B outlet/toko ranking: ambiguity false-positive + alias gaps fixed

Questions like "toko mana yang penjualannya paling tinggi" or "outlet mana yang paling laris" either wrongly triggered the Sell-In/Sell-Out `sales_stage` clarification, or failed outright (`unsupported`/`no_published_metric_match`), despite `gold.corr_b2b_branch_estore_month` already having clean, fast e_store-level aggregates (20,273 distinct outlets, confirmed live: top outlet R472 at Rp156,868,926.64). Root cause: `sales_stage`'s generic "penjualan" trigger ran before B2B-specific alias scoring, and Sell-In's base datasets (`monthly_executive`, `material_360`) have zero outlet/e_store field at all, so the ambiguity was never real. Fixed with a new skip block in `registry.py` (toko/outlet/gerai/e-store language skips `sales_stage` unless the question also explicitly says sell-in/general trade/gross billing), new aliases on `b2b_branch_sell_out_value`/`_quantity`, and adding bare `"toko"` to the `e_store` dimension hint in `context.py` (safe here since this metric has no competing store-level dimension to collide with). All 5 originally-failing phrasings now resolve correctly with `GROUP BY d.e_store`; live-verified against Impala.

### MoM trend ORDER BY fixed (the audit's "no trend metric" claim was wrong — it already worked, just ordered badly)

An earlier gap-analysis claim that "no growth MoM metric exists" turned out to be false: `compile_governed()` already auto-prepends the time dimension to `GROUP BY` whenever a question says "per bulan"/"tren"/"trend". The real bug was `ORDER BY` always sorting by `metric_value DESC/ASC` even for a pure trend question, making "naik atau turun" unreadable from the result order. Fixed: when the trend-prepend fires AND the question has no top-N/superlative ranking intent, `ORDER BY` uses the time dimension ascending instead. Ranking+bulan combos ("top 10 produk bulan ini") are unaffected (still value-ranked) via a `requests_ranking` flag that takes priority.

**Separate, pre-existing, out-of-scope finding** (not fixed this session, needs explicit sign-off before touching): several of `context.py`'s `resolve()` dimensionless shortcuts (`company_fill_rate`, `sat_oos_rate`, `material_fill_rate`, `months_of_stock_cover`, `service_unfulfilled_quantity`) pass an explicit `dimensions=[]`/`["material"]` list into `compile_governed`, which bypasses the trend-prepend/ORDER BY logic entirely regardless of this fix — "tren fill rate per bulan" still does not get a `GROUP BY calmonth` today. Fixing this touches the `resolved()` helper's dimension-passing convention used by every shortcut call site in `resolve()`, so it needs a separate, explicitly-scoped pass.

### Tests

10 new regression tests added to `tests/test_semantic_context.py` (outlet/toko resolution + `GROUP BY e_store`, `sales_stage`/`ratio_direction`/`salesoffice` skip non-regression, trend `ORDER BY d.calmonth ASC`, ranking-with-bulan still `ORDER BY metric_value DESC`). Full suite: **121/121 passing** (111 baseline + 10 new), metric count assertion correctly stayed at 66 except for the one genuinely new metric (`stock_tempo_consignment_qty`, 65→66).

### Not yet done

- Fill-rate/OOS/stock-cover `resolve()` shortcuts' `dimensions=[]` convention blocking trend-prepend (flagged above) — needs a dedicated pass, not bundled into this one.
- `picking_rows_per_sales_line` and `average_picking_minutes`/`average_unloading_minutes`/`picking_delay_rate` already existed with correct row-weighted expressions before this session (only synonyms were added, no new metrics) — verify this is still consistent after the next schema review.
- `datasets/migration/recreate_all_gold_views.sql` is `.gitignore`d — the new `stock_tempo_consignment_qty` metric needed no new view (reused `gold.corr_stock_tempo_month_seta`'s existing `consignment_stock_qty` column), so no view-definition drift this time, but keep flagging this file's gitignore status whenever a *new* view is created.

## Previous checkpoint: dry-run audit, SAT/IDM governance fix, ROI promo proxy, live UAT (1 Oct 2026)

### Context: live Impala access was established this session

Got live Kerberos/GSSAPI access to the Ingram Private Cloud Impala cluster from outside the
CAI environment for the first time - root cause of earlier failed attempts was DNS: the
correct KDC is `cdr-ip.imid.local` (found via `_kerberos._udp.imid.local` SRV record), not
any of the `cbaseNN.imid.local` hosts Impala itself runs on. Once `kinit` succeeded, binary
Impala on port 21050 (the `.env` default) worked fine - the earlier "must use port 28000"
theory from mid-session was a red herring caused by a stale Kerberos ticket, not a real port
requirement. This unblocked direct SQL verification of every finding below instead of relying
on inference from code alone.

### 9-question dry-run audit — 6 fully fixed, 2 by-design partial, verification pending for 1

Audited `[TEMPO SCAN] Dry Run - Resume AI` PDF's 9 findings one at a time, each verified
against live Impala data, not just code inspection:

1. **"stok gudang tempo bro" stuck on Local Agent fallback** — resolver traced end-to-end and
   confirmed correct (resolves to `material_warehouse_stock_quantity`, valid SQL, data exists
   - 5.7B units). The error message in the dry-run screenshot didn't match our own metric
   catalog at all, confirming it came from the separate TEMPO Local Agent, not our planner.
   Most likely cause: the `kerberos` PyPI package (added in `8336980`, 30 Sep) failing to
   build in the live CAI runtime image (needs system krb5 dev headers) - **still needs the
   user to check CAI application logs**, not fixable from this session alone.
2. **"10 cabang dengan service level terbaik/terjelek" returned all-NULL** — fixed. Root
   cause: "cabang" wasn't recognized as a `sales_off` synonym, so the planner picked a
   company/material-level metric instead of `sales_office_service_fill_rate`. Verified live:
   actual fill rates range 41-72%, not NULL. Added "cabang" alias + fixed `sales_stage`
   ambiguity ordering so stock/cover questions aren't hijacked by the generic Sell-In/Sell-Out
   prompt.
3. **"stok produk A di cabang A, cover berapa hari"** — disambiguation fixed (no longer asks
   an irrelevant Sell-In/Sell-Out question), `dimension_mismatch` now correctly flags that
   "cabang" can't be honored by `months_of_stock_cover` (company/material-grain only). Found
   and documented a real data-quality issue during this audit: the metric's 3-month-only
   window (Q4 2024) makes it produce implausible values (e.g. 17,028 "months of cover") for
   low-Sell-In SKUs - confirmed NOT category-specific (both the thin-volume "ERV" material
   group and mainstream high-revenue groups like BCL/TSP show the same pattern), so the
   metric's `ai_context.instructions` now carries an explicit caveat. **Still non-deterministic
   across LLM providers/runs** for the exact phrase "stok produk A di cabang A" - see UAT
   section below; this is a genuine governed-data gap (no branch-level stock metric exists),
   not purely a prompt issue.
4. **"top produk B2B" answered Sell-In after clarification was answered** — fixed. "b2b" was
   missing as a `sales_stage` discriminator, and `material_sell_in_value`'s alias "top produk"
   substring-beat every B2B alias regardless of context. Added "b2b" discriminator plus explicit
   B2B-qualified aliases.
5. **"Top 10 DC Alfamart" returned one aggregate row instead of a per-DC breakdown** — fixed
   and verified against live Impala (DC Palembang highest at Rp 20.87B, etc). Root cause: "DC"
   wasn't recognized as a `branch` dimension hint in `compile_governed()`, so no `GROUP BY`
   was ever added even though the metric's `allowed_dimensions` supports it.
6. **"stok toko alfamart vs DC" comparison** — clarification reworked to distinguish
   "bandingkan" (valid: show both side by side via two follow-up questions) from "jumlahkan"
   (prohibited by Tempo - DC and store stock are different analysis levels). Deliberately did
   **not** build a single-response two-column answer (would require a `compile_governed()`
   architecture change affecting every other metric) and deliberately did **not** route to the
   TEMPO Local Agent fallback for this case - live-tested that agent directly and found it has
   the same SAT/IDM-mixing bug we just fixed on our side (`dimension_filters: part_flag=SAT`
   requested but ignored at execution) plus an unrelated empty-table-rendering bug.
7. **ROI promo** — was a hard `unsupported` refusal; now a `needs_clarification` offering 3
   real proxy metrics (Revenue/Volume/Margin Uplift). See dedicated section below for the full
   investigation and governance additions.
8. **"service level/fill rate cabang tempo, urutkan SL terjelek"** — fixed (same root cause as
   #2), verified resolves directly to `sales_office_service_fill_rate`.
9. **"Analisa unloading dan picking ... perbandingan Industri standard"** — fixed. "picking"/
   "unloading" as bare single words didn't match any alias at all (even individually), so the
   combined question fell through to `unsupported`. Added single-word aliases plus a new
   `_CONCEPT_PATTERNS` entry so a question naming both concepts is now explicitly flagged as
   `multi_concept_metric_mismatch` (both concepts surfaced to the planner) instead of silently
   answering only one. Confirmed via raw-to-gold audit that picking (23/52 sales offices) and
   especially unloading (14/52) coverage gaps are real upstream data limits, not an ETL/join
   bug (raw `silver.picking_okt_des_24`/`unloading_okt_des_24` distinct `sales_office` counts
   match the gold view exactly, 0% loss). Added an explicit no-industry-benchmark-exists
   instruction so the model never invents a comparison figure.

### SAT vs IDM: resolved with Tempo's direct confirmation, not just data inference

**Tempo confirmed directly (Pak Hieronimus Gunawan, 1 Oct 2026, WhatsApp): "utk data sales b2b
2024, hanya SAT (alfamart)"** - B2B/Sell-Out data is Alfamart only. This closes out the
multi-session SAT-vs-IDM investigation definitively: SAT (36 DC, matches B2B 100% by DC name
and by PLU) is the Alfamart partner network; IDM (122 DC/depo/warehouse locations, 0% overlap
with B2B on both DC name and PLU) is a separate, unrelated partner network that happens to
ship in the same source Excel file as a second sheet. Irvan's team independently reached the
same conclusion and added a `part_flag` ('SAT'/'IDM') column to the relevant silver/gold
tables (`silver.stock_sat_idm_monthly_okt_des_24`, `gold.corr_sat_idm_plu_month`,
`gold.rpt_sat_idm_plu_month`); `gold.rpt_b2b_sat_idm_plu_month` was updated (by this session,
after flagging the gap to the user) to join explicitly on `part_flag='SAT'` instead of a
pre-aggregated `_total` view that summed SAT+IDM together - verified the fix changes nothing
numerically (420 rows, identical sums before/after) since no PLU happened to collide, but it
removes the structural risk of silent future mixing.

4 new/renamed gold views deployed live to Impala and reflected in both `tempo_core.ossie.yaml`
and `datasets/migration/recreate_all_gold_views.sql` (gitignored, not committed - see below):
`gold.rpt_sat_dc_month` / `gold.rpt_idm_dc_month` (split from the old combined
`rpt_sat_idm_dc_month`, SAT-only and IDM-only respectively), `gold.corr_b2b_sat_branch_month`
(B2B↔SAT join, explicit `part_flag='SAT'` filter), `gold.corr_sat_dc_oos_material_month`
(renamed from a name that collided with Irvan's own differently-defined, not-yet-reconciled
audit view of nearly the same name). OSSIE metrics renamed `sat_idm_dc_stock_*` →
`sat_dc_stock_*`/`sat_store_stock_*` throughout, with "Alfamart" now stated explicitly instead
of generic "partner" language, everywhere this was previously ambiguous.

### ROI promo: no direct metric exists, but a disclosed cross-channel proxy now does

SAT Promo (`silver.sat_promo_des_24`) has no structured cost column (`mekanisme` is free text
like "POTONGAN 2.600") and covers December 2024 only, with no same-channel prior-month
baseline. Investigated whether `sales_oct_dec_2024`'s `zcost` column could help - it is
labeled "COGS Value" in Tempo's own `silver.custom_key_figure_sales` reference table (not
"out of scope" as an earlier, now-outdated note in `TEMPO_KAMUS_DATA_AI.md` assumed), and its
aggregate COGS/revenue ratio sanity-checks at ~85%, a plausible FMCG distributor margin - but
it lives in General Trade sales data, a different channel from the Alfamart SAT Promo program.
Confirmed structurally valid as a cross-channel ("halo effect") proxy: SAT Promo's 77 SAP
material codes are 100% resolvable against `sales_oct_dec_2024`. Built 2 new gold views
(`gold.corr_sat_promo_material_uplift`, `gold.rpt_sat_promo_material_uplift` - Dec vs Nov
revenue/qty/margin per material) and 3 new OSSIE metrics (`promo_material_revenue_uplift`,
`promo_material_volume_uplift`, `promo_material_margin_uplift`), all carrying explicit
"this is a proxy, not the Alfamart promo's own measured impact" instructions. The `unsupported`
refusal in `registry.py` was changed to a `needs_clarification` offering these 3 variants
instead, with a loop-prevention fix (the clarification answer still contains the words
"promo"/"ROI" from the original question since `contextualize_question()` prepends it, which
previously re-triggered the same clarification forever).

### Two cross-model bugs found via live UAT against GPT-4o and Qwen

Ran the dry-run's 9 questions through the full `ChatService` pipeline (not just the resolver
in isolation) against both `gpt-4o` (OpenAI) and `Qwen3.8-27B-AWQ` (self-hosted, live Impala
backing both). Full transcripts saved verbatim (model output copy-pasted, not summarized) to
`docs/uat/2026-10-01-gpt4o/` (one file per question) and `docs/uat/2026-10-01-qwen-uat.md`
(single compiled file, per user request). Found 2 real bugs neither model-specific, both now
fixed and verified (111/111 backend tests passing throughout):

1. **The LLM query planner was never told what the deterministic resolver already found.**
   When `resolve()` returns `dimension_mismatch` (a matched metric that can't fully cover a
   requested breakdown) or `fallback`/`multi_concept_metric_mismatch` (two+ concepts, e.g.
   "picking dan unloading"), `plan_query()` discarded that signal and handed the LLM planner
   only the raw question plus the full 21-dataset/65-metric catalog - both GPT-4o and Qwen
   sometimes answered `unsupported` for requests a governed metric genuinely covers, simply
   because the specific candidate was never surfaced. Fixed by passing a `resolver_hint`
   object (candidate metric, unmet dimensions, or requested concepts) to the planner prompt;
   `query_planner.md` updated to explain how to use it. Verified fix: question #2 and #9 went
   from inconsistent/unsupported to consistently `SUCCESS` across repeated runs.
2. **SQL validator rejected `CASE WHEN...END` as "Function not allowed: case".** `sqlglot`
   represents `CASE` as an `exp.Func` subtype (`exp.Case`), and `_ALLOWED_FUNCTIONS` in
   `app/sql/validator.py` never included it - a completely standard, safe SQL conditional
   expression was being blocked. Found via Qwen's UAT attempt at question #3 (`gpt-4o` never
   happened to try a `CASE` expression, so this was invisible to the earlier GPT-4o-only UAT
   round). Added `"case"` to the whitelist; verified it fixed question #3 from a hard
   validation error to a correctly-empty `NO_DATA` response (query ran, zero matching rows -
   the honest answer for a literal placeholder "produk A"/"cabang A").

Also found and fixed: metric `ai_context.instructions` text that is too long/verbose appears
to crowd out a model's attention on required output fields (observed: a very long
`months_of_stock_cover` caveat paragraph correlated with the planner omitting the required
`sql` field entirely, "Empty SQL") - shortened while keeping the same substantive caveats.

### Final UAT status (both providers, after all fixes)

| # | GPT-4o | Qwen |
|---|---|---|
| 1 | SUCCESS | SUCCESS |
| 2 | SUCCESS | SUCCESS |
| 3 | unstable (unsupported/validation error across runs - see audit #3 above) | NO_DATA (safe, correct) |
| 4 | SUCCESS | SUCCESS |
| 5 | CLARIFICATION (correct) | CLARIFICATION (correct) |
| 6 | CLARIFICATION (correct) | CLARIFICATION (correct) |
| 7 | CLARIFICATION (correct) | CLARIFICATION (correct) |
| 8 | SUCCESS | SUCCESS |
| 9 | SUCCESS | SUCCESS |

### Not yet done

- User still needs to check CAI application logs for finding #1 (likely `kerberos` package
  build failure in the live runtime image) - not verifiable from outside CAI.
- A third UAT round was requested against `.env`'s `MODEL_OPENAI=gpt-5.6-sol` value to compare
  against the `gpt-4o` run - confirmed the model name itself is valid and reachable via the
  configured API key (verified with a direct API call, using `max_completion_tokens` since
  this model, like `gpt-4o`, rejects the older `max_tokens` parameter), but discovered
  `MODEL_OPENAI` in `.env` does not match any Settings field name (`openai_model` reads
  `OPENAI_MODEL`, not `MODEL_OPENAI`) - **the configured model is not actually wired to
  anything and has never been used**; this needs the user's decision on how to proceed (fix
  the env var name app-side, or pass the model explicitly) before that comparison run happens.
- `datasets/migration/recreate_all_gold_views.sql` is `.gitignore`d (`datasets/**`) - the
  session's edits to it (new/renamed SAT/IDM/promo views) are reflected on disk but were never
  committable; the source of truth for what's actually live is the Impala `CREATE VIEW`
  statements run directly this session, not that file. Flag this if the file is ever relied on
  to recreate the gold layer from scratch again.

## Previous checkpoint: out-of-scope question handling in query_planner.md (30 Sep 2026)

### "unsupported" wasn't reliably chosen for questions outside TEMPO's domain entirely

Live UAT: "Berapa biaya iklan TV Q4 2024" (TV advertising spend - not a TEMPO concept at all, TEMPO only covers sales/stock/OOS/service-level/picking/unloading/promo) got stuck on "Analyzing result" indefinitely instead of returning the `unsupported` message. Root cause: `query_planner.md` told the model to choose `unsupported` "when the requested data is absent" but never explained what TEMPO's scope actually is, so with no negative examples the model tended to force `sql_fallback` by grasping at a superficially-related column (e.g. treating "iklan" as adjacent to "promo" or a price field) rather than recognizing the concept has no real match - producing a plausible-looking but wrong SQL query that then stalls/fails slowly in validation or against Impala instead of failing fast at the planning step. Fixed (uncommitted) by adding an explicit paragraph to `query_planner.md` naming out-of-scope example concepts (advertising/marketing spend, media buying, competitor data, weather, macro figures) and instructing the model to choose `unsupported` immediately when a concept has no genuine match in the supplied `semantic_context.datasets`/`metrics`, rather than substituting a loosely-related column. No test exists that pins prompt file contents, so no test changes were needed; this should be re-verified live against the same "biaya iklan" question once redeployed.

## Previous checkpoint: TEMPO Local Agent fallback, data_reference SQL leak fix, greeting typo fix, branding cleanup (30 Sep 2026)

### TEMPO Local Agent as an opt-in last-resort fallback (`497024e`)

Adopted `reference/tempo-agent-api` (a separately deployed, already-live sibling system at `http://tempo-local-agent.ml-d5612ef4-e6f.apps.ocpb.imid.local/`) as an optional fallback for questions our own OSSIE planner reports as `strategy=unsupported`. Before implementing, read that system's actual code (`router.py`, `tools.py`, `impala_runner.py`) rather than trusting its env vars alone - initial concern from `NEO4J_QUERY_API`/`QDRANT_URL` env vars (looked like an ungoverned vector-search system) turned out to be wrong: Neo4j/Qdrant are only used for routing/semantic search there, and actual data execution always runs a registered `query_id`'s catalog SQL against Impala - "Never accepts ad-hoc SQL" and "SQL composed from governed TEMPO tables (not LLM-generated)" appear verbatim in that repo's own code/docstrings. Live-tested 3 real queries against the running instance before writing any code: Q4 gross sell-in and top-5-by-material answers matched our own OSSIE numbers almost exactly (single-rupiah rounding differences), confirming it reads the same `gold.*` data. Latency was 24-46s per query, and it has its own separate KPI catalog (not guaranteed to agree with ours in every case), so per explicit direction this is presented as a labeled "exploratory" answer rather than a hard refusal - the broader instruction for this session was "answer as much as possible, don't block hard; be honest about confidence via the exploratory label instead."

Zero-risk design: `WorkflowDependencies.local_agent_client` defaults to `None` (inert everywhere unless `LOCAL_AGENT_BASE_URL` is explicitly set); the fallback is only tried inside the existing `strategy == "unsupported"` branch; every failure mode (disabled, timeout, HTTP error, the agent's own refusal) is swallowed and degrades to the exact same `UNSUPPORTED` message that existed before this feature - never a request-level error. New `Strategy` literal `local_agent_exploratory` distinguishes this path in logs/frontend. 12 new tests (8 for `LocalAgentClient`, 4 for the workflow fallback branch), 110/110 backend tests passing at the time.

**Not yet turned on anywhere** - `LOCAL_AGENT_BASE_URL` is not set by default; an operator must opt in explicitly.

### `data_reference` sometimes leaked the raw SQL statement (`82f4899`)

Live UAT screenshot showed a governed answer's "Data reference" section rendering the full `SELECT ... FROM gold.rpt_sap_monthly_executive_semantic d WHERE ...` statement instead of just the view name - `result_analyst.md` doesn't explicitly forbid this, and the model sometimes echoes `query_plan.sql` (received as context) straight into `data_reference`. Rather than relying on prompt compliance (the same lesson repeated across this session's other model-behavior bugs), `data_reference` is now always overridden in code after the model responds: a new `_data_reference_from_sql()` regex-parses the executed SQL's `FROM` clause(s) and replaces `data_reference` with just the `schema.view` name(s) - e.g. `gold.rpt_sap_monthly_executive_semantic` - never the SQL text. Falls back to the model's original value only if no table reference is found (covers the local-agent fallback path above, which already sets its own safe reference).

### Greeting/capability detection broke on a common typo (`abf8965`)

"hallo kamu bintu apa ?" (typo: bintu instead of bantu) was misrouted through the governed/SQL-fallback path and returned `UNSUPPORTED`, instead of being recognized as a conversational capability question like its correctly-spelled sibling already was. Root cause in `_is_conversational_request()` (`backend/app/graph/workflow.py`): the greeting-plus-question form is longer than the plain `short_greeting` word cap, so it only had one path to match (`capability_request`'s regex), and that regex required the literal word "bantu" with no typo tolerance. Fixed by adding a small curated set of one-letter-swap typos for "bantu" (bintu, bnatu, nautu, nato, antuh, natu) plus a shorter word-order pattern - a fixed lookup table for one specific word, not a fuzzy matcher, verified not to create false positives on real business questions.

### Branding/layout cleanup (`0e50b1a`, `a0001d8`)

Several small UI polish items from live screenshots: removed the "BETTER DATA. BETTER AI." tagline and centered the Cloudera brand mark; removed the "Tempo Scan · Ask Data V2" header subtitle and centered "Tempo Scan Intelligence"; dropped "V2" from the sidebar footer ("Tempo Scan V2" → "Tempo Scan"); simplified the chat panel's own header from an icon + "SCAN V2" + "● Governed-first Ask Data" status line down to plain "Scan Intelligence" text.

### Earlier same-day work: chart Y-axis truncation, typography, starter questions (`b636142`..`6351396`, `ae494be`)

- Chart Y-axis values like `300000000000` were clipped by a fixed-width axis; added a compact K/M/B tick formatter, narrowed the axis, kept tooltips at full precision.
- Reduced the bolded direct-answer text size and normalized body text sizing across the response card; replaced the generic Sparkles icon with the existing `ScanMark` monogram (later removed again from the chat panel header per the branding cleanup above); split `data_reference` into a plain note + monospace SQL code block (superseded by the code-level override in `82f4899` above, which now prevents SQL from reaching that field at all).
- Replaced the single "Random Question" button with 3 starter-question cards shown directly on the empty state, fetched once on page load; clicking one submits immediately.
- `query_planner.md`/`result_analyst.md` now instruct the model to set `LIMIT` to match a stated ranking count ("top 5" → `LIMIT 5`) or default to 10, and to never surface more rows than asked for even if the query returned extras - fixes a live case where "top 5 produk" silently showed 30+ rows because the generated SQL had no `LIMIT`.

## Previous checkpoint: V2 Ask Data loading indicator UX pass (30 Sep 2026, latest)

Purely frontend, no backend/governance changes. `frontend/src/views/AskDataPage.tsx`'s loading state (shown while an SSE stream is in flight) went through 3 iterations based on live user feedback against screenshots:

1. **`08cf7c8`**: replaced a single static pulsing dot with 3 staggered bouncing dots (a typical "AI is thinking" animation) plus a pulsing brand mark, and changed the pre-first-event default label from "Understanding request..." to "AI is analyzing..." — the backend's real progress labels (`Understanding request` → `Retrieving semantic context` → `Preparing governed query` → `Validating query` → `Querying TEMPO data` → `Analyzing result`, from `backend/app/services/chat.py`'s `stream()`) still override this as they arrive via SSE, unchanged.
2. **`26783e1`**: the Stop button (at the time, inside the progress pill next to the label) looked cramped against the text — added a vertical divider and more padding/a rose hover state.
3. **`fb83900`**: the user pointed out Claude Code's own pattern - the send button itself (bottom-right of the message composer) swaps into a Stop button in the same position while a request runs, rather than a separate Stop control appearing elsewhere. Replicated that: the composer's submit button now renders as a Stop (square icon, calls the same `stopRequest()`/`AbortController` already in place) when `loading` is true, and the progress pill was simplified back to just the bouncing dots + label with no button of its own.

Verified after each step: `npm test -- --run AskDataPage` (5/5 passing) and `npm run build` (Next.js 15.5.25 production build succeeds) in `frontend/`.

## Current checkpoint: missing `kerberos` package silently broke GSSAPI in isolated venvs (30 Sep 2026, latest)

Live deploy of `backend` to the Private Cloud environment failed with `TTransportException` after one retry. The actual cause was one line above the error, easy to miss:

```text
SASLWarning: kerberos module not installed, GSSAPI will be ignored
```

`puresasl.client` (used by `thrift_sasl`) needs the separate `kerberos` PyPI package (a C extension wrapping the system `libkrb5`) to actually perform GSSAPI operations - `pure-sasl` alone is pure Python and cannot do this itself, despite the confusingly similar name. Without `kerberos` installed, puresasl silently falls back to a non-GSSAPI path instead of erroring loudly, and the server then rejects the connection.

**Why the earlier manual Workbench GSSAPI test (see the "Impala/DWH migration" checkpoint further below) didn't catch this**: that test ran in an interactive Workbench session that apparently had `kerberos` available at the system/global level, outside any project virtualenv. `backend`'s isolated `.venv-cai` and each of the three Impala-backed Agent Studio V1 tools' own sandboxed dependency sets do not inherit anything from that global environment - each needs the package listed in its own requirements file.

**Fix** (commit `8336980`): added `kerberos==1.3.1` to `backend/requirements-impala.txt` and to all three Impala-backed V1 Agent Studio tools' `requirements.txt` (`execute_governed_query`, `execute_readonly_sql`, `execute_governed_metric_query`) - harmless to also have it present for LDAP/PLAIN-only deployments like the old AWS environment.

**Not yet verified**: this package needs system Kerberos dev headers (`krb5-devel` / `libkrb5-dev`) present at pip-install/build time. If the CAI runtime image lacks them, installing `kerberos` will fail to build - that would be a separate environment/infra issue to flag, distinct from this code fix. Redeploy `backend` (and re-import the V1 tools if revisited) and confirm the package actually builds and installs before assuming this is fully resolved.

## Current checkpoint: SAT OOS, Service Level, and request cancellation hardening (30 Sep 2026)

- Natural SAT OOS questions now resolve before generic stock-scope handling. Overall survey OOS, material-level OOS, and customer/store-level OOS route to `sat_oos_rate` with the governed dimensions.
- Requests asking how much OOS caused sales to decline are rejected as unsupported causal analysis instead of being redirected to a Sell-In/Sell-Out clarification and eventually returning an unrelated sales total.
- Common Service Level questions now select the published company, material, sales-office, and PO-minus-DO metrics deterministically.
- Impala HTTP 401/403 failures are classified as `IMPALA_AUTH_FAILED`, are not retried, and return a safe operator-facing message without exposing credentials or driver details. LDAP readiness now requires both username and password; GSSAPI continues to rely on the Kerberos service identity.
- The frontend streams with an `AbortSignal`, shows a **Stop** control during active requests, clears loading state after cancellation, and automatically aborts requests after 90 seconds.
- Deployment documentation now clearly separates the legacy LDAP/HTTP profile from the current Private Cloud GSSAPI/TLS/binary profile.

Verification for this checkpoint: backend V2 **96 passed** (2 dependency warnings only), frontend V2 **15 passed**, and the Next.js 15.5.25 production build passed. Live Impala execution still requires correcting the CAI authentication profile and restarting the application before UAT is repeated.

## Current checkpoint: Stock SAT-IDM UAT hardening (30 Sep 2026)

- Explicit partner-DC wording such as `stok di DC partner` and `DC mana` now resolves directly to `sat_idm_dc_stock_quantity`; the assistant no longer repeats the generic warehouse/DC/store clarification.
- Retail wording including `stok toko`, `stok retail`, and store variants is recognized as the store-level SAT-IDM scope.
- Requests to add DC Stock and Store Stock are intercepted before metric selection, including Indonesian `stok toko` phrasing. The response preserves the governed rule that both levels may be shown separately but cannot become one synthetic pipeline total.
- “Sekarang”, “saat ini”, and “bulan ini” compile against the latest governed snapshot (December 2024): `calmonth = 202412`, or `thn = 2024 AND bln = 'DEC'` for SAT-IDM, rather than summing three monthly inventory snapshots.
- Low-stock rankings recognize natural phrases such as `paling kecil`, `paling rendah`, and `paling sedikit` and order ascending.
- Every stock ranking defaults to ten rows and explicit requests above ten are capped at ten. This replaces the 50-row stock outputs that made charts and tables unreadable during UAT.
- The UAT document now records the observed Stock SAT-IDM failures, including the critical live response that incorrectly added DC and store stock.

Verification for this checkpoint: backend V2 **82 passed** (2 dependency warnings only). Live Impala values still require re-running the affected UAT questions after the CAI application is restarted.

## Current checkpoint: V2 CAI UAT fixes — conversational context and compact model payloads (30 Sep 2026)

The V2 application now addresses the three linked failures seen in CAI:

- Greetings use the selected LLM with a dedicated friendly system prompt and a compact Ossie-derived capability catalog. Only greeting detection is deterministic; wording remains model-generated, with a safe local fallback if the provider is unavailable. First-turn and later-turn greetings are distinguished using session history.
- The existing SQLite conversation store is now read as well as written. A lightweight contextualizer combines a short Sell-In/Sell-Out clarification reply with the immediately preceding question, while excluding stored result rows from model prompts.
- “Gross sales untuk top 5 produk” is resolved to the governed material-grain metric `material_sell_in_value`, not the company-level `gross_billing_value`. Generated SQL uses `gold.rpt_sap_material_month_semantic`, applies `has_sell_in = TRUE`, groups by material, orders by `metric_value DESC`, and limits to five.
- `planner_context()` now recognizes both business-domain names and exact Ossie dataset names. Governed analysis therefore receives only the selected dataset and its metrics; the reproduced top-product payload fell from roughly 22,000 characters / 20 datasets / 62 metrics to roughly 3,000 characters / 1 dataset / 11 metrics.
- Qwen/OpenAI-compatible and Gemini HTTP failures now log safe diagnostics containing provider, status, normalized error code, and endpoint path without API tokens or request payloads.
- Frontend answers now emphasize the direct answer, use status-aware headings/colors, and separately render insights, business implications, caveats, data reference, visualization/table, and muted model metadata.

Follow-up CAI conversational UAT hardening:

- Fixed the greeting `Empty SQL` failure by separating the four valid `QueryPlan` strategies from the response-only `conversational` strategy. A model can no longer return a conversational query plan that accidentally continues into SQL validation.
- Conversational routing now recognizes natural greeting sentences and capability exploration such as “apa yang bisa dibantu?”, “bisa apa lagi selain sales?”, and “data stok bisa keluarin apa saja?”. The detector only selects the route; the selected LLM still writes the answer.
- The conversational system prompt now uses progressive guidance: broad questions offer domains, domain-level questions offer governed sub-options and examples, and specific context is turned into an executable question rather than another static menu.
- Guidance payloads are built from the Ossie metric catalog. Stock exploration includes the available warehouse, partner-DC, and retail-store metrics plus governed dimensions/examples; “selain sales” is explicitly represented as an excluded topic.
- Lightweight history resolution now understands short choices from any clarification fields, not only Sell-In/Sell-Out. `stok retail` is also a governed discriminator/synonym for `sat_idm_store_stock_quantity`, preventing a repeated stock-scope clarification.

Latest follow-up and presentation refinement:

- Sell-In/Sell-Out clarification replies are canonicalized before being joined to the previous question. Both `sell in` and `penjualan Tempo ke customer` now preserve the original “top 5 produk” intent and resolve to `material_sell_in_value` grouped by material, instead of falling back to a company total or adding customer grain.
- The result-analysis prompt is intentionally flexible: simple factual questions stay direct, while ranking or richer analysis leads with the useful conclusion and uses the other answer sections, table, or chart only when they improve readability. It does not enforce a rigid response length or structure.
- AI answers, capability guidance, caveats, and result tables use larger typography and a wider response canvas.
- Bar-chart rankings whose series value is unique on every row are rendered as one clean ranking series with composite category labels instead of a noisy one-customer-per-series legend. Charts also have taller plotting space, bounded bar width, and larger axis/legend labels.
- The Ask Data header now provides one accessible full-screen toggle for both desktop sidebars. It slides the Cloudera navigation out, collapses the conversation-history grid track, and expands the chat canvas with synchronized 300 ms transitions; toggling again restores both sidebars. Mobile bottom navigation and the Settings-page navigation remain unchanged.

Verification at this checkpoint:

- Backend V2: **68 passed** (2 dependency warnings only).
- Frontend V2: **12 passed**.
- Frontend V2 production build: **PASS** on Next.js 15.5.25.
- Local semantic probe confirmed `material_sell_in_value` and the required non-null coverage filter for the reported top-five question.
- Local runtime has no model credentials and no live Impala connection, so the final Qwen/Gemini/OpenAI and data-value smoke tests remain deployment-environment steps.

Next CAI checks: pull this commit, restart the backend and frontend applications, retry the exact top-five question, retry the Sell-In clarification sequence in one session, and test a greeting once with each configured model.

## Decision: stop iterating on the V1 Agent Studio Backstory for this bug class, use V2 instead (30 Sep 2026, later same day)

The exact same failure ("gross sales untuk top 5 produk" wrongly answered at company-level instead of material-level) was fixed and independently re-broken 3 times in the V1 Agent Studio + ChatGPT workflow across the checkpoints below, despite each fix being verified correct at the resolver level via direct simulation every time:

1. Resolver didn't flag the mismatch at all → fixed (`6467465`, earlier session).
2. Resolver flagged it (`dimension_mismatch`), but the Backstory never told the agent to act on the signal → fixed (`1604e9d`).
3. The Backstory's own suggested retry wording ("Gross Billing Value (Sell-In) ... breakdown per produk") still matched the wrong metric → fixed (`db1e3c2`).
4. ChatGPT over-simplified the first call to something with zero matching candidates, then treated `unsupported` as "no governed metric exists" and jumped straight to an ungoverned SQL fallback → fixed (`3402b25`).
5. Backstory was condensed (228 → 144 lines) to reduce reasoning-chain length as a suspected cause of point 4 → done (`6103414`).
6. **Still failed after all of the above, and confirmed model-agnostic, not ChatGPT-specific**: an initial live trace attributed to ChatGPT showed this failure, but a second live trace on the SAME question using the private Qwen model (not ChatGPT) showed the identical failure pattern - the agent's own stated retry intent ("I'll retry with plain wording") did not match the tool call it actually sent (still contained "gross sales sell-in"), and the same odd "re-summarize the tool/metric-catalog JSON repeatedly" loop appeared in both traces. This is an execution-consistency failure when chaining multiple tool calls with carried-over conversational context that reproduces across at least two different underlying models (Qwen and ChatGPT), not a single model's quirk, and not a gap in the resolver or the instructions - both were re-confirmed correct for this exact question via direct simulation immediately before this conclusion. Root cause is more likely in the Agent Studio orchestration layer (e.g. how "Ask question to coworker" context/history is assembled across a multi-tool-call chain) than in any one model's instruction-following.

**Decision**: stop spending further iterations on the V1 Agent Studio Backstory for this specific bug class. The V2 application (`backend`/`frontend`, see checkpoint above) already handles this exact question correctly, verified live via CAI UAT with a real screenshot (Rp 786,892,979,793 for the same "top 5 produk" question) - V2's fix lives in code (`planner_context()`'s Ossie-derived dataset/metric selection, not an LLM-authored natural-language retry), which does not depend on a chat model (or Agent Studio's orchestration of one) consistently executing multi-step retry reasoning correctly. Treat V1 Agent Studio as a frozen reference/demo channel going forward for this class of question; put further governed-analytics effort into V2.

The Backstory fixes above are still correct and still committed - they were not reverted, since they do measurably reduce (not eliminate) the failure rate and remain the best available version if V1 Agent Studio is ever revisited. They are just not being iterated on further.

## Previous checkpoint: V1 Agent Studio Backstory fix — dimension_mismatch was not acted on (30 Sep 2026, later same day)

Commit `1604e9d`, pushed. Found while executing `docs/uat-questions-2026-09-29.md` (the authoritative 46-question UAT set) live against the OLD AWS Agent Studio environment, since the new Private Cloud environment's Agent Studio is still blocked on the sandbox permission issue in the checkpoint below.

**What happened**: asking "berapa total gross sales Q4 berdasarkan top 5 produk" through the ChatGPT-backed `TEMPO Master Agent` → `TEMPO Data Agent` workflow returned a confident-looking company-level Gross Sales total (Rp 3,841,865,787,073) with no product breakdown — framed as "the governed metric doesn't support this breakdown," which is false; `material_sell_in_value` exists and is governed for exactly this.

**Root cause, confirmed by testing the tool directly in Agent Studio's Tools Playground** (bypassing the LLM agent entirely): `execute_governed_metric_query`'s resolver correctly matched `gross_billing_value` AND correctly flagged `"dimension_mismatch": ["material"]` in its response — the fix from commit `6467465` (the original "top N product" bug) is intact and working. The bug is one layer up: nothing in the Data Agent's Backstory told it to act on a non-empty `dimension_mismatch` by re-resolving with the dimension folded in. The tool executes with whatever `dimensions` list the caller passes — it does not auto-correct. GPT-4.1/Qwen apparently inferred the right move on their own in earlier testing; ChatGPT did not, and instead misread the mismatch as "this metric can't do that."

**Fix**: added two `CRITICAL` paragraphs to `projects/tempo_scan_impala/agents/AGENT_STUDIO_3AGENT_SETUP.md`'s Data Agent Backstory (one for the 3-separate-tools path, one for `execute_governed_metric_query`) instructing it to re-call the resolver with the mismatched dimension explicitly folded into the question and passed in `dimensions`, and to report `unsupported` rather than presenting the wrong-grain number if that still fails. Purely additive — only triggers when `dimension_mismatch` is non-empty, so cases that already worked (including on Qwen/GPT-4.1) are unaffected.

**Not yet done**: the updated Backstory text needs to be manually pasted into the live `TEMPO Data Agent` in Agent Studio (both the old AWS workflow and, once unblocked, the new Private Cloud one) — editing the file in this repo does not change what's running live, per this project's established pattern (Agent Studio tools/Backstories are copy-pasted in via the UI, not synced from git). Re-test the same question after pasting to confirm ChatGPT now retries correctly.

**UAT progress**: this was found on UAT question Sales/Sell-In #3 ("Produk apa aja yang paling laku sepanjang Q4?", though tested with a slightly different phrasing). `docs/uat-questions-2026-09-29.md`'s Hasil/Status columns have not yet been filled in with this or any other result — that's still pending. Continue the domain-by-domain UAT execution against the old AWS environment once the Backstory fix is pasted in and re-verified.

## Previous checkpoint: TEMPO Scan Commercial Intelligence V2 implemented (30 Sep 2026)

### Scope delivered

- **Separate applications**: `backend/` (FastAPI) and `frontend/` (Next.js), each with its own CAI launcher, dependencies, environment example, tests, and deployment documentation. V1 remains intact.
- **Controlled backend workflow**: understand request → retrieve Ossie context → governed or fallback query planning → SQL validation → Impala execution → answer/chart generation.
- **Governed-first behavior**: Ossie metric and dimension metadata is preferred. Unsupported business questions may use a clearly marked SQL fallback, subject to read-only SQLGlot validation, table allowlisting, row limits, and function allowlisting.
- **Pluggable LLM providers**: Qwen private/OpenAI-compatible, Google Gemini, and OpenAI. Provider selection is controlled by backend environment variables; API keys remain backend-only.
- **Frontend experience**: streaming Ask Data chat, progress events, table/chart/KPI rendering, session history, model discovery/selection, settings, and curated random-question discovery.
- **Question coverage**: 30 curated examples across the governed business domains, including paraphrase handling and explicit expected contracts.
- **No Agent Studio dependency**: V2 is a conventional frontend/backend application pair and does not depend on the blocked Agent Studio tool sandbox described in the previous checkpoint.

### Provider configuration and validation

Secrets must be supplied as CAI environment variables and must never be committed. The deployment operator must set the model identifier as well as the credential/base URL:

- Gemini: `GEMINI_API_KEY`, `GEMINI_MODEL` (live probe passed with `gemini-3.8-flash`).
- OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL` (live probe passed with `gpt-5.6-sol`). The adapter uses `max_completion_tokens` and does not send an unsupported fixed temperature to this model family.
- Private Qwen: `QWEN_BASE_URL`, `QWEN_MODEL`, and `QWEN_API_TOKEN` when the endpoint requires a token. `QWEN_API_KEY` remains accepted as a backward-compatible alias. A live `QueryPlan` structured-generation probe passed against the deployed Qwen CAI endpoint after the schema-correction hotfix.

Both configured public-provider keys passed their respective `/models` authentication checks and an end-to-end structured-generation adapter probe. No credential values are recorded in this file or the repository.

### Impala authentication profiles

V2's Impala driver is environment-driven and passes through authentication, TLS, HTTP transport, HTTP path, user/password, and Kerberos service settings. It supports both deployment families currently in scope:

- **Legacy environment / LDAP**: typically LDAP auth, port 443, TLS enabled, HTTP transport enabled, HTTP path `cliservice`, and CAI-injected username/password.
- **New Private Cloud / Kerberos**: GSSAPI auth, port 21050, TLS enabled, binary transport, and Kerberos service name `impala`; username/password are not required by the readiness rule.

The committed `.env.example` is intentionally secret-free and currently emphasizes the GSSAPI profile. Before deploying to the legacy environment, operators must override the full LDAP setting group. Separate named LDAP/GSSAPI template files and stricter profile validation were discussed but are **not part of this checkpoint**. Live connectivity must be tested from the actual CAI network/runtime because DNS, certificates, Kerberos tickets/keytabs, and LDAP credentials are environment-owned.

### CAI deployment and initial sizing

Deploy as two CPU-only CAI Applications; the private Qwen/vLLM service, if used, is a separate deployment and sizing concern.

| Application | Recommended start | Minimum PoC | Scale-up starting point |
|---|---:|---:|---:|
| Backend V2 | 4 vCPU / 8 GiB RAM | 2 vCPU / 4 GiB | 8 vCPU / 16 GiB |
| Frontend V2 | 2 vCPU / 4 GiB RAM | 1 vCPU / 2 GiB | 4 vCPU / 8 GiB |

The backend should receive provider secrets, Ossie paths/settings, and the selected Impala auth profile. The frontend should receive only the public backend URL. Both launchers bind to the CAI-provided application port; health/readiness endpoints should be verified before exposing the frontend to users.

### CAI launcher compatibility hotfix

- Both V2 launchers now work when CAI executes the selected Python file as Jupyter/IPython interpreter cells, where `__file__` is undefined. Checkout discovery follows the proven V1 pattern: inspect `CDSW_PROJECT_DIR` and the current working directory first, and use the script path only when it exists.
- Both launchers now follow V1's CAI lifecycle pattern: start Uvicorn/Next.js with `subprocess.Popen`, keep the interpreter kernel alive while monitoring the child process, and terminate it cleanly on shutdown. The earlier `os.execve` handoff caused the CAI engine to exit after a successful frontend build.
- Frontend portable Node was raised from 20.18.1 to 20.19.0 to satisfy the installed Vite toolchain's declared Node engine requirement. The Linux x64 archive URL was verified available from `nodejs.org`.
- Qwen deployment configuration now accepts the environment's established `QWEN_API_TOKEN` name. `QWEN_API_KEY` remains a backward-compatible alias.
- Qwen structured generation now receives the exact Pydantic JSON Schema in the leading system message. If Qwen returns valid JSON with the wrong field contract (observed live as `plan_type`/`clarification`/`reasoning` instead of `strategy`/`clarification_question`), the adapter performs one correction retry containing the invalid response and the exact schema instead of failing the whole Ask Data request immediately.
- The Backend CAI dependency bootstrap now pins `thrift==0.16.0`, the exact version required by `impyla==0.22.0`. The earlier V2 pin to Thrift 0.22.0 caused pip `ResolutionImpossible` before Uvicorn could start. A real `pip install --dry-run --ignore-installed` now resolves the complete Impala requirement set successfully.
- Regression tests explicitly execute both launchers in a namespace without `__file__` and verify that the correct V2 directories are found.

### Verification evidence

- Backend V2: **47 tests passed**.
- Frontend V2: **8 tests passed** and the production Next.js build completed successfully.
- V1 regression protection: backend **454 tests passed**; frontend **71 tests passed**.
- CAI launcher/readiness dry-run coverage passed in the backend V2 suite.
- Live Gemini and OpenAI adapter probes passed with the intended model IDs; a live Qwen `QueryPlan` probe also passed against the deployed private endpoint.
- Production-source secret audit found no embedded API keys.
- Live Impala queries were not run from this local workspace; both LDAP and GSSAPI profiles still require in-environment smoke tests.

### Next actions

1. Push the V2 checkpoint commit to the shared remote when ready.
2. Create backend and frontend CAI Applications using the launchers and environment examples in their directories.
3. Inject the selected LLM provider configuration and exactly one matching Impala auth profile.
4. Verify backend `/health` and `/health/ready`, then run a direct Impala smoke query in the target environment.
5. Point the frontend at the backend URL and execute governed, fallback, history, visualization, and negative-control UAT flows.

## Previous checkpoint: Impala/DWH migration to Private Cloud on-prem + Kerberos support (30 Sep 2026)

Follow-up to the "testing-driven resolver fixes" checkpoint below. 5 commits since then, all pushed to `origin/main`:

```
690ac74 docs: note Qwen URL scheme and model path leading-slash gotchas found during Private Cloud deploy
d10f42c fix: add Kerberos (GSSAPI) support for Impala and re-point tool sandbox path
340d590 feat: add Sales/Sell-In transaction-line gold view for dashboard tools
3a9853c fix: Data Agent Backstory told execute_governed_metric_query to send follow-ups "verbatim"
39f0f83 fix: gross_billing_value synonyms required the word "gross", broke plain "sell-in" follow-ups
```

(Plus 8 earlier commits between the previous checkpoint and this one — semantic layer audit against a colleague's separate model, a golden-question fix, and doc work. Full list: `git log --oneline 497ff21..690ac74`.)

### DWH migration: AWS (S3/Iceberg) → Private Cloud on-prem

The data warehouse moved from Cloudera-on-AWS (Iceberg tables on S3) to a Cloudera Private Cloud on-prem cluster, hostname `cbase02.imid.local`, realm `IMID.LOCAL`. Migration mechanics (distcp, path structure) are documented in `docs/dwh-migration-checklist.md`. As of this checkpoint the migration itself is **done** — `silver.*` tables exist and are queryable on the new cluster.

**Full Gold layer recreate script**: `datasets/migration/recreate_all_gold_views.sql` (gitignored — `datasets/**` is excluded except allowlisted paths, this file was not force-added). 57 `CREATE VIEW IF NOT EXISTS` statements, assembled from `datasets/audit/*.sql` + `datasets/gold/*.sql` (no new view logic introduced, "_fixed" revisions used where they exist), split into 9 sections:

1. Baseline `corr_*` views (9)
2. Baseline `rpt_*` views (5, using "_fixed" revisions)
3. `_semantic` wrappers (5) — what `tempo_core.ossie.yaml`'s datasets actually reference
4. SAT Promo (1)
5. Journey expansion (9) — Stock Tempo → Sales → B2B → SAT-IDM → SAT OOS
6. 28 Sep customer/sales_office breakdown expansion (5)
7. Dashboard-only view (1) — `rpt_sales_sell_in_line_semantic`, NOT in the governed OSSIE contract
8. **21 views from a colleague's (Irvan's) separate `view from irvan/` migration folder — NOT wired into OSSIE, each tagged PERLU VALIDASI / QA-ONLY / REFERENCE in the file's comments.** Two real findings from this audit: (a) `corr_sat_oos_material_month` in that folder uses a **different OOS definition** than our governed `sat_oos_rate` (`stok_akhir <= 0` vs our `= 0`, coarser grain) — a real definition conflict, not just "unverified"; (b) `corr_sat_idm_plu_month` there is built from a source table whose own comment admits bronze/silver currently loads only the first xlsb sheet — possible incomplete IDM data. Do not adopt anything from section 8 into the OSSIE YAML without resolving these first.
9. `rpt_semantic_metric_catalog` — documentation-only view (metric metadata as rows via UNION ALL), deliberately last per its own "DEPLOY LAST" comment.

Run this file once (single Workbench block) against the new cluster's `gold` database, then re-run `scripts/validate_tempo_impala_contract.py --json` to confirm the governed 20/62/82 dataset/metric/golden-question contract still holds.

**Audit of Irvan's semantic model is NOT finished.** Only section 8's SQL definitions were read and compared; the planned next steps (audit the ~10 new metrics unique to Irvan's 76-metric model vs the 66-metric one already audited in `docs/irvan-semantic-model-audit.md`, then write a combined decision doc) were not reached before the session moved to Agent Studio migration. Pick this back up before treating the DWH migration as fully closed on the semantic-layer side.

### Kerberos (GSSAPI) support added to the Impala backend

The new cluster requires **GSSAPI auth over TLS** — confirmed by direct `impyla` probing from a Workbench session (every non-GSSAPI/non-SSL combination failed with `TSocket read 0 bytes`; GSSAPI+SSL succeeded, then verified end-to-end through the actual `Settings`/`ImpalaBackend` code path, not just raw `impyla`). Working combination: `auth_mechanism=GSSAPI`, `use_ssl=True`, `port=21050`, binary transport (`use_http_transport=False`), `kerberos_service_name="impala"`.

Code changes (commit `d10f42c`):

- `backend/app/core/config.py`: new `impala_kerberos_service_name: str = "impala"` Settings field.
- `backend/app/db/impala_backend.py`: passes `kerberos_service_name` through to `impyla.connect()`.
- All 3 Impala-backed Agent Studio tools (`execute_governed_query`, `execute_readonly_sql`, `execute_governed_metric_query`) got the same new `UserParameters` field + env var plumbing.
- All 7 tools' `config.json` sandbox mount changed from `/home/cdsw/enterprise-ai-poc` to `/workflow_data/enterprise-ai-poc` — the new environment's actual project volume mount path for Agent Studio (confirmed by the user; this is NOT the same path a plain interactive Workbench session sees, which is still `/home/cdsw/enterprise-ai-poc` — the two are different mount points for different container types in this environment).
- New test in `backend/tests/test_impala_backend.py`: `test_impala_query_passes_kerberos_service_name`. All 6 tests in that file pass.

**Verification helper**: `datasets/migration/test_impala_connection.py` (gitignored, not committed). Two modes: default runs a raw `impyla.connect()` probe across several transport/port/SSL/auth candidates; `--backend` flag instead exercises the real `Settings()`/`ImpalaBackend()` code path with env vars set exactly as `_apply_impala_env()` in the tool files does. Both modes confirmed working on 30 Sep 2026 from a Workbench session at `/home/cdsw/enterprise-ai-poc`. Keep this file around for the next environment migration — re-verifying through `--backend` (not just raw `impyla`) is what caught that a passing raw probe doesn't guarantee the app's env-var plumbing agrees.

### Known blocker: Agent Studio sandbox fails on every tool, in the new environment

Not a code issue — this is an infrastructure/container-runtime problem in the new Private Cloud environment. Reproduced identically on 2 different tools (`execute_governed_query`, `execute_readonly_sql`) via Agent Studio's own Tools Playground, which runs a tool in isolation before it ever reaches the tool's Python code:

```
bwrap: Can't bind mount /oldroot/etc/resolv.conf on /newroot/etc/resolv.conf:
Unable to remount destination "/newroot/etc/resolv.conf" with correct flags: Permission denied
```

`bwrap` (bubblewrap) is Agent Studio's tool sandboxing mechanism; this error means it cannot create a Linux user namespace, which happens before any tool code runs — so this cannot be fixed from inside a tool, from the Agent Studio UI, or from this repo. Full write-up with likely causes (`kernel.unprivileged_userns_clone=0`, Kubernetes pod security context blocking `CAP_SYS_ADMIN`, or SELinux/AppArmor) and what to ask infra to check: `datasets/migration/agent-studio-sandbox-permission-issue.md` (gitignored, not committed — copy its content directly to whoever has node/cluster access). **The user has node/cluster access themselves** (no separate infra team) — this was handed to them directly rather than escalated externally. Status as of this checkpoint: unresolved, migration paused here.

### UAT question set exists but has never been executed

Three separate UAT/acceptance documents exist in the repo, and **none of them have ever had their results filled in**:

1. `docs/qa/2026-09-28-agent-studio-nine-domain-acceptance.md` — 9 domain smoke-test scenarios + 4 SAT Promo safety checks + 1 SQL-fallback check. All rows still say "pending". Its "frozen local contract" baseline (15 datasets/50 metrics/75 questions) is now stale vs. the actual current contract (20/62/82) — update this if it's ever actually run.
2. **`docs/uat-questions-2026-09-29.md` — the authoritative UAT file** (confirmed by the user 30 Sep 2026). 46 natural-language business questions across the 9 domains (32 expected to resolve as governed, 14 deliberately out-of-scope and expected to be refused/clarified). Result/Status columns are empty for every row.
3. `datasets/TEMPO_UAT_SESSION.md` — older, 20 prescriptive/diagnostic cross-domain questions (e.g. "sell-in high + fill rate low — prioritize fulfillment?"). Log sheet is empty and not even fully listed (20 rows expected, only a template row present).

**In progress at the end of this session**: the user started executing `docs/uat-questions-2026-09-29.md` live against the OLD (AWS) Agent Studio environment, since the new environment's Agent Studio is blocked on the sandbox issue above. Domain-by-domain, starting with Sales/Sell-In (#1-9). No results had been recorded yet when this checkpoint was written — pick this up by asking the user for the next domain's Agent Studio output and filling in the Hasil/Status columns per the file's own FAIL/PARTIAL grading guide (see that file's "Panduan cepat untuk auditor" section — flag Stock SAT-IDM question #4 in particular, a DC+Store summation that Tempo has explicitly confirmed must never happen).

### Historical plan: v2 backend + frontend rewrite, using ChatGPT instead of Claude

This was the handoff request at the end of the previous checkpoint. It is now implemented by the V2 checkpoint above; the paragraph is retained only to preserve the chronology of the project history.

## Previous checkpoint: testing-driven resolver fixes + customer/sales_office breakdowns (28 Sep 2026, later same day)

Follow-up session to the nine-domain expansion below, triggered by live Agent Studio testing with the user. 11 commits, all pushed:

```
497ff21 docs: sync Agent Studio setup docs with live production config
6467465 fix: resolve "top N product" questions to the material-grain metric
e0819ce fix: strengthen SQL fallback disclaimer to a plain-language confirmation ask
95e4f44 feat: add customer and sales_office breakdowns to Sales/Sell-In
25de172 docs: audit B2B/Stock SAT-IDM/SAT OOS/Service Level for the same breakdown gap
85fd9b0 feat: add customer breakdown to B2B/Sell-Out
5401c06 feat: SAT Promo status confirmed as all-active, unblock plain "promo aktif" questions
e9b1dfc fix: split B2B customer gold views into separate single-statement files
7a87ecb docs: record B2B gold view Workbench verification and ka_group data quality note
8752e1a feat: add sales_office breakdown to Service Level
12f0134 docs: record Service Level gold view Workbench verification
```

### What triggered this session

The user ran a live testing conversation in Agent Studio with a colleague. Two findings:

1. **"top 5 produk" resolved to the wrong metric.** A follow-up question ("...top 5 produk apa aja yang penjualannya paling besar") resolved to the company-level `gross_billing_value` (calmonth-only, no product breakdown) instead of `material_sell_in_value`. Root cause, two layers: (a) `dimension_terms["material"]` in the deterministic resolver only recognized Indonesian hints ("produk"), not English ("product"); (b) structurally, `resolve_with_llm_fallback()` only ever consulted the LLM classifier when the deterministic matcher returned `"unsupported"` — a confident-but-wrong `"resolved"` result never got a second opinion. Fixed both the immediate synonym gap and the structural gap: `resolve_metric()` now reports a `dimension_mismatch` list when the winning metric's `allowed_dimensions` doesn't cover a dimension the question hinted at, and `resolve_with_llm_fallback()` no longer short-circuits when that list is non-empty — it only overrides if the LLM classifier succeeds AND returns a genuinely different metric, so it can only improve the deterministic answer, never make it worse. This same structural fix caught two more instances of the identical bug pattern later in the session (see below) before they shipped.
2. **The user asked whether the system is ready for broader Indonesian-language variation**, and separately whether AI-generated SQL beyond the 50 governed metrics is safe. Led to strengthening `execute_readonly_sql`'s disclaimer from a technical "governed: false, verify manually" string to an explicit plain-Indonesian confirmation ask ("Mohon konfirmasi kebenaran angka ini dengan tim terkait sebelum dipakai untuk keputusan bisnis"), required to lead the final answer verbatim — not just a technical flag most users would never parse.

### Customer/sales_office/group breakdown expansion

The user asked to strengthen Sales, B2B, Stock SAT-IDM, SAT OOS, and Service Level with customer/sales_office/group dimensions, since a lot of real business questions ("top customer", "which sales office") need them. Audited each domain against its field catalog before writing anything, rather than assuming:

| Domain | Outcome |
|---|---|
| Sales/Sell-In | ✅ Expanded — `customer` and `sales_off` both existed in `silver.sales_oct_dec_2024` but were never exposed past `calmonth`+`material`. New: `gold.rpt_sap_customer_material_month_semantic`, `gold.rpt_sap_sales_office_material_month_semantic`. |
| B2B/Sell-Out | ✅ Expanded — `silver.b2b_oct_dec_2024`'s source row already carries customer+material+sales_off+branch+e_store+ka_group together. New: `gold.corr_b2b_customer_branch_estore_month`, `gold.corr_b2b_customer_material_plu_month`. Data-quality finding, not a bug: `ka_group` is the literal constant `"101"` for all 4,881,348 rows this period — documented, not exposed as a meaningful dimension. |
| Service Level | ✅ Expanded — `sales_off` existed in `silver.service_level_oct_dec_2024` but unused. New: `gold.corr_service_sales_office_material_month`. Two other candidate columns deliberately excluded: `c_0cust_grp3` is confirmed constant ("SL") for the whole period (would never produce more than one group); `c_0af_cgr6` varies but its business meaning is explicitly unconfirmed by Tempo per the field catalog — excluding an unexplained code is better than exposing it as a governed dimension. |
| Stock SAT-IDM | ❌ Not possible — `TEMPO_STOCK_SAT_IDM_FIELD_CATALOG.md` states plainly "Tidak ada customer/store di SAT-IDM"; it's a DC/store stock snapshot, not a per-customer/sales_office transaction feed. No new data source, no expansion possible. |
| SAT OOS | Partially already governed, rest not possible — `cust_id`/`cust_code` were already dimensions on `gold.rpt_sat_oos_material_month`, no gap there. `sales_office` is not possible: `TEMPO_SAT_OOS_FIELD_CATALOG.md` states explicitly "Tidak ada kolom: sales office, cabang, region..." — the SAT OOS source is a separate 6-column Excel file, not a SAP BW export, and never had that column. |

`sales_office`/`sales_off` throughout this expansion is a working PoC assumption ("a branch in a given region"), per a direct instruction — `TEMPO_SALES_FIELD_CATALOG.md` still marks `0SALES_OFF` as "asumsi PoC, follow-up Tempo," not yet a Tempo-confirmed business definition. Every new metric using it carries that caveat forward in its `ai_context.instructions`, same treatment as the pre-existing `sales_office_sell_in_value`/SI-13-Q4.

All three new/extended gold views were run in Workbench and verified — not just written:

- **Cardinality/null checks**: clean (0 null/blank key columns) for all three.
- **Duplicate-grain checks**: `0` rows for all three views.
- **Reconciliation**: `SUM()` from each new view, rolled up to calmonth only, matched the pre-existing governed company-level total exactly for all three months in every case (float/DECIMAL(38,2) trailing-digit noise only for money values; exact match with zero noise for Service Level's raw quantities).

One Workbench lesson from this session, useful if it recurs: running two `CREATE VIEW` statements (with a comment between them) as one highlighted block threw a `ParseException` — the editor appears to execute a highlighted range as a single statement rather than splitting on `;`. Fixed by splitting the B2B gold view file into two single-statement files (`25a_*.sql`, `25b_*.sql`); the Service Level view was written as a single statement from the start and needed no split.

### SAT Promo: program_status confirmed all-active

Tempo (Pak Hieronimus Gunawan, WhatsApp, 28 Sep 2026) replied "abaikan saja pak, di list tersebut, artinya aktif" to "Y = active kah?" — interpreted per direct instruction as: every row in the SAT Promo December data is an active promo observation, regardless of its `program_status` code (Y/X/T). This does not make `program_status` a meaningful active/inactive discriminator — it establishes the opposite, that the whole dataset is already active, so status can't be used to carve out an inactive subset. Previously the resolver blocked any "promo aktif"-shaped question outright; that block was too broad and is now narrowed to only block questions implying an active/**inactive** split (never confirmed), not a plain "promo aktif" question (now resolves to `promo_observation_count`). Removing the block alone wasn't sufficient — the metric also needed an actual "promo aktif" synonym added before the deterministic resolver could match it, caught by this session's own new test before shipping.

### Updated contract numbers

- **20 datasets** (was 15 in the previous checkpoint below; net +5: 2 Sales, 2 B2B, 1 Service Level).
- **61 metrics** (was 50; net +11).
- **81 golden questions** (was 75; net +6, plus 2 test-file-only regression questions not counted in the YAML total).
- Contract validator: `valid=true`, no errors.
- Focused OSSIE/Agent Studio/Impala suite: **106 passed** (`test_tempo_ossie_service.py` 75 + `test_tempo_impala_contract.py` 11 in one run, plus `test_tempo_agent_studio_tools.py` 31 separately).

### Next actions, in order

Unchanged from the previous checkpoint's plan, now current:

1. Push the local `main` commits to `origin/main` (this PROJECT_STATE.md update is itself part of that push).
2. Pull the updated `main` branch in the Cloudera Workbench checkout.
3. Run `scripts/validate_tempo_impala_contract.py --json` in Workbench and confirm `20 datasets / 61 metrics / 81 golden questions`.
4. Rebuild `workflow_data/enterprise-ai-poc`, redeploy `Tempo-Scan-Intelligence-Prod`, and verify the deployed artifact contains the updated OSSIE model, governance, golden questions, and tool files.
5. Execute the nine-domain UI/API acceptance matrix in `docs/qa/2026-09-28-agent-studio-nine-domain-acceptance.md` — now includes a dedicated SQL-fallback-disclaimer section added this session, plus the customer/sales_office breakdown questions should be spot-checked live even though they're verified against Impala directly.
6. Only after the Agent Studio baseline passes, begin the deferred Semantica implementation assessment/PoC (still explicitly deferred, not started).

---

## Previous checkpoint: nine-domain semantic layer (28 Sep 2026, earlier same day)

### Repository state

- Semantic implementation commit: `bc517b7 feat: expand TEMPO semantic layer to nine domains`.
- Previous planning commit: `b4ea934 docs: design full TEMPO metric coverage`.
- `origin/main` is still at `a3bc9fb`; the planning, implementation, and this checkpoint update are local-only and still need an explicit push.
- The semantic expansion commit contains the OSSIE model, resolver/governance changes, business-question catalogs, Gold/audit SQL, Agent Studio instructions, tests, and acceptance evidence.

### Frozen semantic contract

- **9 domains**: Sales/Sell-In, B2B/Sell-Out, Stock Tempo, Stock SAT-IDM, SAT OOS, Service Level, Picking, Unloading, and SAT Promo.
- **15 OSSIE datasets**.
- **50 governed/candidate metrics**.
- **75 golden questions**.
- Contract validator result: `valid=true`, with no validation errors. Metrics marked `pending business confirmation` remain intentional governance warnings, not technical failures.
- Latest verification before commit:
  - Full backend suite: **449 passed**, 2 dependency deprecation warnings.
  - Next.js production build: **PASS**.
  - Focused OSSIE/Agent Studio/Impala suite: **104 passed**.

### Business definitions locked into the model

- Stock SAT-IDM DC Stock and Store Stock are separate analytical levels. They must never be added into a synthetic total-pipeline metric or converted into an unapproved imbalance/ratio KPI.
- Sales and B2B terminology is explicit: `bill_qty`/`bill_val` are billing quantity/value; `do_qty`/`do_amt` are Delivery Order quantity/amount.
- B2B branch and Tempo sales office are separate dimensions and are not aliases.
- SAT OOS represents field-audit availability at the evaluated DC or B2B unit.
- SAT Promo currently supports December 2024 observation counts and distinct-material counts by raw `mekanisme` and raw `program_status`.
- SAT Promo `program_status` values `Y`, `X`, and `T` remain raw/unmapped codes. The workflow must not call them active/inactive/success/failed until Tempo supplies the controlled definition.
- Promo ROI, uplift, cost, attributed revenue, and October-November trend remain intentionally unsupported because the available source does not govern those claims.

### SAT Promo Gold status

Canonical view: `gold.rpt_sat_promo_material_december_semantic`.

- View successfully deployed in Cloudera Workbench using Impala-compatible `DROP VIEW IF EXISTS` + `CREATE VIEW` syntax.
- Semantic rows: **297**.
- Source observations represented: **67,837**, exactly matching the Silver source total.
- Duplicate canonical-grain rows: **0**.
- Negative observation rows: **0**.
- Rows outside December 2024: **0**.
- Null/blank material rows: **0**.
- Evidence: `datasets/qa/23_sat_promo_gold_contract.md`.

### Agent Studio deployment status

The existing production workflow remains live with the earlier latency and stability improvements, but it has **not yet been redeployed with the new nine-domain OSSIE bundle**.

Next actions, in order:

1. Push the local `main` commits to `origin/main` when approved.
2. Pull the updated `main` branch in the Cloudera Workbench checkout.
3. Run `scripts/validate_tempo_impala_contract.py --json` in Workbench and confirm `15 datasets / 50 metrics / 75 golden questions`.
4. Rebuild `workflow_data/enterprise-ai-poc`, redeploy `Tempo-Scan-Intelligence-Prod`, and verify the deployed artifact contains the updated OSSIE model, governance, golden questions, and tool files.
5. Execute the nine-domain UI/API acceptance matrix in `docs/qa/2026-09-28-agent-studio-nine-domain-acceptance.md`, including SAT Promo happy paths and safety controls.
6. Only after the Agent Studio baseline passes, begin the deferred Semantica implementation assessment/PoC. Current work is assessment documentation only (`docs/SEMANTICA_ASSESSMENT.md`); no additional Cloudera AI Application has been created for Semantica.

---

**⚠️ Historical handoff note (earlier on 28 Sep 2026, before the nine-domain expansion)**:

Everything through commit `ea5f5f7` is committed and pushed to `origin/main`. Today's session was almost entirely Agent Studio production debugging + latency optimization, working live against the deployed `Tempo-Scan-Intelligence-Prod` workflow via its REST API (`createSession`/`kickoff`/`events` — see below). Recent history (newest first):

```
ea5f5f7 feat: add execute_governed_metric_query tool to shorten the Data Agent's LLM chain
76c3690 chore: gitignore reference/ - found live-looking credentials in it
bf9e47d fix: follow-up questions to the agent_studio backend had no context
d28e10e refactor: render Agent Studio's Markdown answers verbatim instead of parsing them into a fixed card
758e5ac fix: numbered lists collapsed into one run-on Key Drivers paragraph
5bd7df1 fix: add anti-buffering headers to /chat/stream so progress actually streams
b452391 fix: analysis was disappearing from Ask AI answers, empty drivers/caveats
69d6a13 fix: chatStream() was dropping the terminal done frame on Cloudera AI
7bfdfec fix: send SSE keep-alive heartbeats to survive CAI's proxy idle timeout
02ec1b8 feat: stream Agent Studio progress to Ask AI instead of a static spinner
738901e feat: add Agent Studio chat backend behind CHAT_BACKEND env var flag
```

### What actually got fixed today (in the order they were found)

1. **`CHAT_BACKEND=agent_studio` wired up** (`738901e`) — `backend/app/services/chat.py`'s `run_chat()` now branches on `settings.chat_backend`: `"graph"` (default, unchanged LangGraph path) or `"agent_studio"` (new — calls the deployed Agent Studio workflow's REST API and adapts its Markdown output). Requires 3 new env vars on the `tempo-backend` CAI Application: `CHAT_BACKEND=agent_studio`, `AGENT_STUDIO_BASE_URL` (the workflow's own base URL, e.g. `https://workflow-a9ac1dd9-....cloudera.site`), `AGENT_STUDIO_API_KEY` (a Cloudera AI API v2 key, same as `$CDSW_APIV2_KEY` in a session).
2. **SSE progress streaming** (`02ec1b8`, `7bfdfec`, `69d6a13`, `5bd7df1`) — `POST /api/chat/stream` streams `{"type": "progress", "label": "..."}` frames (translated from raw Agent Studio events into natural Indonesian, e.g. "Mengambil angka dari data governed...") while the multi-agent chain runs, then one final `{"type": "done", "response": ChatResponse}`. Took 3 follow-up fixes to actually work end-to-end against Cloudera AI's own reverse proxy and the browser's `ReadableStream` behavior — see "Non-obvious infra lessons" below.
3. **Markdown rendered verbatim, not parsed into a fixed card** (`b452391`, `758e5ac`, `d28e10e`) — the original design tried to extract `summary`/`drivers`/`caveats` from Agent Studio's Markdown answer by pattern-matching section headings. This kept breaking (exact-heading mismatch, then a numbered-list answer got flattened into one run-on paragraph) because real Analysis Agent answers vary in shape more than a fixed schema can represent. Replaced with `react-markdown` + `remark-gfm` rendering the Markdown directly (`ExecutiveAnswer.markdown` field, `MarkdownAnswer` component in `AskAIPage.tsx`); `markdown_chart_adapter.py` now only extracts the first table for `chart_spec`/`ChartSpec` (Recharts still needs structured data — everything else is untouched raw Markdown).
4. **Follow-up questions lost context** (`bf9e47d`) — `agent_studio_client.stream_workflow()`/`run_workflow()` both accept a `context` param, but nothing was passing one, so every question went to Agent Studio standalone. Fixed by loading the last assistant turn's Markdown from `ConversationStore` and passing it as `context` — the Master Agent's own Backstory already defines a `FOLLOW_UP` envelope for this, it just never received input to build one from.
5. **`execute_governed_metric_query` — new combined Agent Studio tool** (`ea5f5f7`) — biggest latency win. Colleague Irvan's separate Agent Studio workflow (`reference/workflow irvan/`, gitignored — **found live-looking credentials in `demo_config.py`, tell Irvan to rotate them**) uses a single-agent/single-tool/no-delegation design (`crew_ai_allow_delegation: false`) that answers in ~1-2 LLM calls by wrapping an entire resolve→query→execute pipeline in one Python tool call. Adopted that pattern for just the Data Agent's three technical tool calls: `projects/tempo_scan_impala/agent_studio_tools/execute_governed_metric_query/tool.py` runs `resolve_with_llm_fallback` → `get_metric_definition` → `execute_query` (the exact same `TempoOssieService` calls the 3 standalone tools already used) as one Python function instead of three separate LLM-driven ReAct tool calls. Master Agent and Analysis Agent (LLM narration) were deliberately left untouched.

### Agent Studio manual fixes applied today (not in this repo — done directly in the Agent Studio UI, not version-controlled)

- **Registered `execute_governed_metric_query` as a 5th tool on TEMPO Data Agent** (the 3 original tools — `resolve_semantic_object`, `get_metric_definition`, `execute_governed_query` — were kept attached, not removed, as a fallback for edge cases like re-executing with different filters against an already-resolved metric).
- **Added a "Preferred tool" section to TEMPO Data Agent's Backstory** instructing it to call `execute_governed_metric_query` once instead of the three separate tools for standard metric questions.
- **Added a "Response length policy" section to TEMPO Analysis Agent's Backstory** — simple single-metric questions now get a 2-3 sentence answer (still always including `metric_id`/`source_view`/governance caveat) instead of the full Ringkasan/Implikasi Bisnis/Status structure, which is now reserved for genuinely complex questions (breakdowns, trends, ratios, or an explicit request for analysis).
- **Fixed a recurring Master Agent bug**: the Master Agent's Backstory few-shot examples used the coworkers' display **Name** (`"TEMPO Data Agent"`, `"TEMPO Analysis Agent"`) in the `"coworker"` field of every `Ask question to coworker` tool call, but CrewAI matches coworkers by **Role** (`"TEMPO Governed Data Retriever"`, `"TEMPO Business Insight Explainer"`), not Name. This caused the Master Agent to fail its first delegation attempt on nearly every turn and silently self-correct with a retry — wasting one full LLM round-trip every time. Fixed by rewriting every `"coworker"` value in the Backstory's few-shot examples to use the Role string.

**Net result**: a simple single-metric question (e.g. "Berapa Company Fill Rate selama Q4 2024?") now completes in **~20 seconds** (Data Agent ~13s including one fast tool call, Analysis Agent ~7s with the short-form response) — down from the original 3-agent chain's ~9 LLM calls taking 40-60+ seconds. Confirmed via live testing directly in the Agent Studio "Test" tab (Thoughts panel timing), not just theoretical.

### Non-obvious infra lessons from today (useful if this recurs)

- **Cloudera AI's own reverse proxy aborts SSE connections that go quiet** (`net/http: abort Handler` from a Go/gin component, not app code) if no bytes flow for a stretch — fixed with a `: keep-alive\n\n` SSE comment heartbeat every 15s during Agent Studio's polling gaps. Also needed explicit `X-Accel-Buffering: no` / `Cache-Control: no-cache, no-transform` headers, or an intermediate layer buffered the *entire* SSE response before forwarding it (progress looked frozen, then the whole answer appeared at once).
- **Browser `ReadableStream.getReader().read()` can report `done: true` in the same call that delivers the final chunk**, not only in a separate empty final read — a naive `if (done) break` before processing that chunk's buffer silently drops the last SSE frame(s), including the terminal `{"type": "done"}` payload. `frontend/src/lib/api.ts`'s `chatStream()` now always drains the buffer before checking whether to stop.
- **Agent Studio matches `"coworker"` in a delegation tool call by the coworker's Role field, not its Name field** — easy to get backwards when writing few-shot examples by hand (see above).
- **`markdown_chart_adapter.py`'s repeated fragile-parsing failures were symptomatic, not a one-off bug** — every fix (exact heading match → keyword match → per-line exclusion → numbered-list support) fixed one shape of Agent Studio's Markdown output but broke on the next variation. The actual fix was to stop parsing meaning out of free-form Markdown at all and render it verbatim; this is documented in the module's own docstring now as the reasoning, not just "here's how it works."

### Colleague Irvan's parallel Agent Studio infrastructure — confirmed live, not just code

Irvan has separately built and deployed (confirmed via CAI Applications screenshot, all "Running" for 3-5 days under project "Semantic M...", user `izarkasie`): **Vector DB** (Qdrant), **Graph DB** (Neo4j), and several iterations of **Workflow: TEMPO KPI Analyst** (v1.4.4 through v1.4.6, single-agent/single-tool/no-delegation architecture — see point 5 above). His KPI catalog (`TEMPO_KPI_query_catalog.json`, generated 2026-09-24) has **66 KPIs/measures** cataloged vs our 39 governed metrics — covers our 5 in-scope domains plus promo/pricing/assortment/qa/executive/finance/lead_time. Not yet integrated or reused beyond the `execute_governed_metric_query` architectural pattern above — his tool itself was not called from our workflow. Worth a direct conversation with Irvan about whether his Neo4j/Qdrant instances are meant to be shared infrastructure for this project or his own scoped experiment, and about the `demo_config.py` credential rotation.

### Next planned work (not started yet — this is what the ChatGPT handoff below is for)

The user's explicit next step: **expand the OSSIE semantic layer to the domains that aren't governed yet**, informed by the latest meeting with the Tempo team. Current coverage snapshot (from `datasets/TEMPO_BUSINESS_QUESTIONS_CATALOG.md`'s 165-question catalog, gitignored but present on disk):

| Domain | Total Qs | Governed now | Needs new Gold view | Out of scope |
|---|---|---|---|---|
| Sales/Sell-In | 15 | 5 | 7 | 3 |
| B2B/Sell-Out | 15 | 11 | 2 | 2 |
| Stock SAT-IDM | 15 | 9 | 6 | 0 |
| SAT OOS | 15 | 6 | 9 | 0 |
| Stock Tempo | 15 | 8 | 7 | 0 |
| Service Level | 15 | 6 | 6 | 3 |
| Unloading | 25 | 9 | 16 | 0 |
| Picking | 25 | 11 | 10 | 4 |
| **SAT Promo** | 25 | **0** | 21 | 4 |
| **Total** | 165 | 65 | 84 | 16 |

SAT Promo has zero coverage (no Gold view exists at all). The user mentioned having fresh input from a recent Tempo team meeting specifically about the Sales domain that hasn't been incorporated yet — that should shape prioritization before building anything.

Older handoff context (3-agent Agent Studio build-out, 25 Sep 2026) is preserved below in the next section — still accurate as history, just no longer the most recent work.

<details>
<summary>Previous handoff note (25 Sep 2026, switching from Claude Code to Codex) — historical, superseded above</summary>

Everything through commit `ec19a8d` is committed **and pushed** to `origin/main` — no local-only commits pending. Recent history (newest first):

```
ec19a8d feat: accept Impala credentials as Agent Studio User Parameters
376da58 fix: lazy-import backend implementations in build_data_backend()
ddb095f feat: add 3-agent Cloudera Agent Studio workflow (Master, Data, Analysis)
eec480a fix: validateChatResponse rejected every response after adding data.unit_format
2ef48b8 feat: generate governed answer narratives with the LLM instead of a static template
283334d fix: format governed metric values by their declared unit, not by field name
d6df38a feat: add LLM fallback for governed metric resolution
9bbff4a fix: relax OSSIE registry validator to a minimum, not an exact count
f450314 fix: add missing langdetect to backend/requirements-lock.txt
eb59d27 fix: sync venv with requirements.txt on every CAI backend start
6734d64 feat: add 9 journey Gold views (Stock Tempo→Sales→B2B→SAT-IDM→OOS) to OSSIE semantic layer
ffc7d4e refactor: make OSSIE/Impala the permanent default, remove legacy semantic layer from the request path
```

**Immediate next step — Agent Studio end-to-end test is mid-flight, not finished:**

The 3-agent Cloudera Agent Studio workflow (`TEMPO Master Agent` → `TEMPO Data Agent` / `TEMPO Analysis Agent`, docs in `projects/tempo_scan_impala/agents/AGENT_STUDIO_3AGENT_SETUP.md`) is now fully built in the UI: all 4 custom tools (`resolve_semantic_object`, `get_metric_definition`, `execute_governed_query`, `execute_readonly_sql`) exist in the Tools Catalog and are attached to TEMPO Data Agent, each with `project_root=/home/cdsw/enterprise-ai-poc` set, and the two Impala-backed tools (`execute_governed_query`, `execute_readonly_sql`) additionally have `impala_host`/`impala_port`/`impala_database`/`impala_auth_mechanism`/`impala_user`/`impala_password`/`impala_use_ssl`/`impala_use_http_transport`/`impala_http_path` filled in as User Parameters (see commit `ec19a8d` for why — Agent Studio's tool Configure UI only exposes User Parameters, no separate env-var section, so credentials are threaded through `UserParameters` → `os.environ` inside each tool before `Settings()`/`TempoOssieService()` is constructed).

Testing via the full agent conversation ("Berapa Gross Sales Q4 2024?") initially showed `resolve_semantic_object` failing inside the Data Agent. **Root cause confirmed and resolved (25 Sep 2026, later same day)**: it was a stale CAI Workbench checkout predating the `376da58`/`ec19a8d` fixes — after `git pull origin main` in the Workbench terminal, the exact same manual command now succeeds cleanly:

```bash
cd /home/cdsw/enterprise-ai-poc
python3 projects/tempo_scan_impala/agent_studio_tools/resolve_semantic_object/tool.py \
  --user-params '{"project_root": "/home/cdsw/enterprise-ai-poc"}' \
  --tool-params '{"question": "Berapa Gross Sales Q4 2024?"}'
# -> {"status": "resolved", "metric": "gross_billing_value", "matched_alias": "gross sales",
#     "definition": {..., "unit_format": "currency_idr", ...}}
```

This confirms the `duckdb` lazy-import fix, the LLM-fallback resolver, and `unit_format` are all working correctly against the real CAI environment. **Not yet done**: this was validated via the manual terminal command only, not yet re-tested through the full Agent Studio agent conversation (the earlier UI test predates this fix). Next actions, in order:

1. Re-run the same "Berapa Gross Sales Q4 2024?" question through the actual Agent Studio conversation (not the terminal) and confirm TEMPO Data Agent now succeeds end to end (resolve → get_metric_definition → execute_governed_query, the last one requiring the Impala credentials configured in `ec19a8d` to actually connect and return real Q4 2024 numbers).
2. If `execute_governed_query` or `execute_readonly_sql` show trouble (these are the only 2 of the 4 tools that touch Impala), validate them individually with the same manual-terminal-first approach before assuming the agent conversation UI's error is the full story.
3. Once the governed path works end to end, run the full test scenarios from `AGENT_STUDIO_3AGENT_SETUP.md` §4 (governed path, ungoverned SQL-fallback path via `execute_readonly_sql`, and the negative-control `DROP TABLE` rejection).

**Known Agent Studio quirks hit so far** (all worked around, not blockers):
- Gemini as the LLM backend threw `litellm.BadRequestError ... "Requests ending with a model turn are not supported"` specifically when the Manager Agent delegated to a sub-agent (not on direct replies) — switching to a GPT model in the same workflow made this go away; root cause in Agent Studio's Gemini message formatting was not investigated further.
- The combined system prompt across all 3 agents exceeded Qwen3.8-27B-AWQ's 4096-token context window before any tool was even attached — fixed by shortening each agent's Backstory to terse bullet points (routing rules, numbered pipeline, gates) rather than prose. If more agents/tools are added later and this recurs, shorten further or pick a larger-context model if one becomes available.
- This version of Agent Studio (v2.3.0-b40) has no separate "Tools Playground" for isolated per-tool testing before attaching to an agent — validate tools either by running `tool.py` manually in a Workbench terminal (fastest for real errors) or by testing through the full agent conversation. The agent conversation UI only ever shows the agent's own friendly fallback wording on tool failure, never the underlying Python traceback — always cross-check with a manual terminal run when something looks wrong.
- Each tool's Configure UI in Agent Studio only exposes fields declared in that tool's `UserParameters` Pydantic model — there is no separate environment-variable configuration surface per tool. Any external config a tool needs (Impala credentials, feature flags, etc.) must be declared as an explicit `UserParameters` field and copied into `os.environ` inside `run_tool()` before importing anything from `backend/app/`.

Older handoff context (OSSIE/Impala cutover, 24 Sep 2026) is preserved below in "Live Impala cutover + resolver fixes + legacy cleanup (24 Sep 2026)" further down this file — still accurate, just no longer the most recent work.

This is a running snapshot to paste into ChatGPT (where the original plan/milestones live) to sync it with what's actually been built.

</details>

---

## Architecture (as built)

Three deployed CAI Applications, one shared FastAPI backend:

1. **tempo-frontend** — Next.js 15 (App Router), TypeScript, Tailwind, Recharts. Pages: Dashboard, Ask AI, AI Monitoring, Settings.
2. **tempo-backend** — FastAPI + LangGraph orchestration (`backend/app/graph/`). Serves `/api/dashboard`, `/api/chat`, `/api/health`.
3. **qwen-38-awq / vLLM Application** — `testing/model/vllm/` — self-contained CAI Application: builds its own venv, starts `vllm serve` with `--reasoning-parser qwen3 --default-chat-template-kwargs`, then a FastAPI proxy in front of it (message normalization for Agent Studio/LiteLLM compatibility).
4. **(optional) LiteLLM routing layer** — `litellm/` — 4th CAI Application, routes through a `commercial-intelligence` model group with an `agent-studio-workflow` placeholder group that falls back to `commercial-intelligence` if unavailable. Default-off, backward compatible.

**Data backend & semantic layer (current defaults, changed 24 Sep 2026)**:
`backend/app/core/config.py` now defaults to `project_id="tempo_scan_impala"`, `semantic_execution_mode="ossie"`, `data_backend="impala"`. OSSIE/Impala — governed real TEMPO Q4 2024 data via Apache Ossie — is the permanent path for Ask AI and the Dashboard, not an opt-in profile anymore. The old DuckDB-synthetic semantic layer (`app/semantic/{resolver,intent}.py`, the SQL-generation/graph nodes it powered) has been deleted from the live request path entirely.

**Forecast / weather / market intelligence — kept but disconnected**: these three modules (`app/forecasting/`, `app/external_signals/weather/`, `app/market_intelligence/`) still query DuckDB-synthetic tables directly and have not been retargeted to Impala. Rather than delete them, they were explicitly excluded from this cleanup (forecasting is a standing tool the user wants kept by default; market intelligence's data relevance is still an open question — both to be discussed separately). Their code, tests, and `projects/tempo_scan/semantic/*.yaml` config all remain intact, but `route_intent`/`workflow.py` no longer route anything to them — they are unreachable from Ask AI until a future decision is made. Internally they now read `settings.legacy_synthetic_project_id` (`"tempo_scan"`, a new dedicated setting) instead of the shared `project_id` default, since that default now points at `tempo_scan_impala`.

**Conversation memory**: custom `ConversationStore` (`backend/app/services/conversation_store.py`) — plain synchronous SQLite, `MAX_HISTORY_MESSAGES = 20`. (A LangGraph `AsyncSqliteSaver` checkpointer was tried first and abandoned — it had a correctness bug causing exponential checkpoint file growth, several GB within minutes. Documented as a hard "don't retry this" in project memory.)

**Guardrails**: Guardrails AI (`guardrails-ai` package + Hub validators `DetectJailbreak`, `SecretsPresent`), auto-installed at CAI Application startup via `ensure_guardrails()` in `backend/app_cai_backend.py`, gated by `GUARDRAILS_ENABLED`/`GUARDRAILS_TOKEN` env vars.

---

## What's done (chronological, condensed)

**Backend correctness/governance fixes** (the biggest chunk of work):
- Fixed the AI fabricating answers with the wrong metric (e.g. answering "how many customers" with a Net Sales figure) instead of admitting data isn't governed. Two rounds, root-caused as `measure_request_terms` list gaps + `route_intent` and `resolve_semantics` using divergent keyword sets.
- Fixed a systemic language-detection bug: 7 places compared `state["language"] == "id"` directly, but the frontend always sends `"auto"`, so every deterministic fallback silently defaulted to English. Fixed via one `_resolve_language()` helper.
- Fixed evidence table columns/data getting mixed up across conversation turns in the same session (React state bug: `state.chat.table.columns` was global, shared by every rendered message).
- Fixed caveats (governance/data-availability disclaimers) never reaching the UI at all. The field existed in API responses but no component rendered it. Also had to strip raw internal status codes (e.g. `METRIC_NOT_CONFIGURED`) that would have leaked into caveats once rendering was added.
- Fixed a guardrail bypass: phrasing like "data customer tidak governed, kasih tau aja" was quietly answered instead of getting an explicit disclaimer.
- Fixed forecast/weather fallback responses: language inconsistency, and irrelevant "recommended actions" showing up when there was no data to act on.
- Made `direct_chat` (greetings/small talk) call the LLM for a natural reply instead of a fixed template, so it can actually respond to whatever was asked ("bisa bahasa Indonesia?", "siapa kamu?") instead of only recognizing hardcoded greetings.
- Robotic phrasing fixed: raised `ANALYSIS_TEMPERATURE` to 0.35, added a `CONVERSATIONAL_TEMPERATURE` of 0.5, rewrote system prompts for natural analyst/colleague phrasing.

**UX/product fixes**:
- `npm ci` no longer re-runs on every frontend restart (marker file).
- Fixed 5 UX issues in one pass: floating AI not syncing to dashboard, "New Chat" not creating real sessions, floating→Ask AI handoff re-triggering the same question, follow-ups not working, no persistent memory.
- Renamed the assistant to **SCAN** (Smart Commercial Analytics Navigator) throughout.
- Added a "SCAN Test Plan" artifact (~50 manual test scenarios across greeting, analytical, metric-unavailable, forecast, weather/market, out-of-scope, guardrail, multi-turn, visualization, session-management categories). Used to drive most of the correctness fixes above.

**vLLM / Agent Studio incident (biggest single debugging session)**:
- Agent Studio kept failing with `litellm.BadRequestError: System message must be at the beginning.` Took a long path through several wrong hypotheses (proxy message-ordering, missing vLLM CLI flags, corrupt venv, missing compiler for a Triton kernel) before finding the real root cause: `_resolve_base_dir()` in `app.py` used a wildcard glob (`base.glob("*/vllm")`) that could silently match an old, abandoned folder (`/home/cdsw/tempo_llm_vllm_test/vllm/`) instead of the real project folder, so the Application was sometimes launching uvicorn against stale, unfixed code no matter how many times it was restarted or even recreated from scratch. Every file-content check looked correct because it was always checking the *intended* checkout, not the one actually running.
- Diagnosed by adding a throwaway `/debug-version` endpoint + build marker to the proxy and curling it directly. A 404 was the proof that stale code was serving traffic.
- Fixed with an exact, non-wildcard path check. Confirmed working via direct curl tests (including a deliberately out-of-order `[user, system, user]` payload) and then in Agent Studio itself.
- Along the way also fixed: `app.py` now builds its own project-local venv instead of depending on a global `vllm` install (`~/.local`) that doesn't survive a CAI container rebuild; auto-rebuilds the venv if it's corrupt/incomplete; passes `--reasoning-parser qwen3 --default-chat-template-kwargs` to `vllm serve` (needed for this specific model's GDN/reasoning architecture).
- Lesson captured in project memory: if a CAI Application keeps behaving like it's running different code than what's on disk, don't trust `git log`/file-content checks alone. Add a version-marker endpoint and curl it, since that's the only way to prove what a *running process* actually loaded.

**UI/product decision — floating AI removed**:
- The Dashboard's floating "Ask AI" chat drawer was removed entirely after a UX review. It duplicated Ask AI's chat UI almost exactly (same fields, different markup), used a separate session, and needed a manual "Continue in Ask AI" handoff. Confusing, and already drifting (caveats had been added to one and not the other).
- **Ask AI is now the single chat surface.** It still applies AI-driven dashboard state changes (filters, highlights) via `applyDashboardAiActions`, carries undo history, shows as "Applied by AI" with a working Undo on the Dashboard even though the chat that triggered it lives on a different page.
- Dead code removed: `DashboardAssistant`, `DrawerAnswer`, `dashboardAiActions.ts` (deleted outright), the drawer-only focus-scroll mechanism, the sessionStorage chat handoff.

**Latest round — tone, icons, layout polish (most recent)**:
1. SCAN's conversational tone made warmer/more casual (system prompts now explicitly ask for "sharp colleague," not "formal corporate assistant"), locked to **saya/Anda** consistently. An earlier pass let it drift to aku/kamu mid-conversation, which read as inconsistent rather than warm. Fixed on user feedback after live testing.
2. Em dashes (—) and en dashes (–) explicitly banned from all LLM-generated output (both conversational and analytical system prompts). Was reading as visibly AI-generated.
3. (Not a code change, a recommendation) The Agent Studio "General Prompt / System Instruction" field is separately editable in the Agent Studio UI itself. Gave the user a rewritten draft prompt matching the same warmer, no-em-dash voice.
4. Replaced the generic Sparkles/Bot icons in Ask AI with a plain "S" monogram (`ScanMark` component). Matches the avatar pattern already used for the user's own initials and the sidebar brand mark, reads as part of the product instead of a generic AI widget.
5. Removed the Dashboard's page title/subtitle (`PageIntro`). Filters now sit directly under the app shell header instead of under a repeated "Commercial Dashboard" heading. "Last refreshed" moved into the filter row.
6. Sales Performance chart card split: line chart (left) + a metrics panel (right) showing Best month, Period average, Latest month-over-month move, and Forecast delta when available. Computed client-side from existing trend data, no backend change needed. Previously it was just a bare line chart.
7. Body font switched from Inter (near-universal AI-tool-template default) to **Plus Jakarta Sans** via `next/font/google`, self-hosted.
- User reviewed the result live and confirmed it reads as natural now, with one fix requested (pronoun consistency, #1 above, already applied).
- Also confirmed: the current Ask AI message bubble layout (user bubble right-aligned within its own max-width, AI card left-aligned within its own max-width, both within a full-width panel) is **intentionally kept as-is**. A comparison against Gemini's centered-narrow-column style was raised and then explicitly rejected in favor of the current layout.

---

## TEMPO real-data Impala + Apache Ossie profile (24 Sep 2026)

This is a **parallel, default-off migration path**. It does not overwrite the
existing `tempo_scan` synthetic foundation.

### Physical and semantic audit

- Existing CDP pipeline confirmed: 12 Silver Iceberg tables and 36 Gold views.
- Sales scaling confirmed: Silver Sales values are 1/100 IDR; Gold applies
  ×100 exactly. Official revenue remains `BILL_VAL` / Gross Billing Value.
- `gold.rpt_sap_material_month` grain (`calmonth + material`) validated unique.
- Five audited semantic wrapper views were created in Impala:
  - `gold.rpt_sap_monthly_executive_semantic`
  - `gold.rpt_sap_material_month_semantic`
  - `gold.rpt_service_level_material_month_semantic`
  - `gold.rpt_sap_customer_reconciliation_semantic`
  - `gold.rpt_sales_office_performance_semantic`
- Runtime metadata view: `gold.rpt_semantic_metric_catalog`.
- Semantic Contract v1: 28 metric definitions across 5 views.
  - 21 adapted from Irvan's KPI catalog.
  - 7 derived during audit.
  - 26 pending TEMPO business confirmation.
  - 2 internal technical/data-quality metrics.
- Source-controlled DDL, audits, field catalog, provenance, and final checks:
  `datasets/audit/`.

### Isolated real-data project

New profile: `projects/tempo_scan_impala/`.

- Official Apache Ossie root-schema model: 5 datasets, 28 metrics.
- Governance rules: Q4 scope, Sell-In/Sell-Out ambiguity, official revenue,
  no free SQL, no invented joins.
- 31 candidate management/golden questions with supported, clarification,
  unsupported, and blocked outcomes.
- Current candidate coverage: 19 supported/supported-with-caveat, 1
  clarification, 10 intentionally unsupported scope tests, 1 blocked free-SQL
  request. A real 30–50 question management inventory is still required.
- Apache Ossie official schema validation: **PASS**.
- Internal semantic contract validation: **PASS**.

### Additive backend/runtime

- New `backend/app/ossie/` registry, resolver, deterministic compiler, query
  executor, and LangGraph nodes.
- New read-only API surface:
  - `/api/semantic/status`
  - `/api/semantic/capabilities`
  - `/api/semantic/resolve`
  - `/api/semantic/ontology`
  - `/api/semantic/join-path`
  - `/api/semantic/compile`
  - `/api/semantic/query`
- Feature flag remains default-off:

```text
SEMANTIC_EXECUTION_MODE=legacy
OSSIE_PROJECT_ID=tempo_scan_impala
```

- OSSIE execution requires `DATA_BACKEND=impala`; no ungoverned fallback is
  attempted.
- Existing canonical `ChatResponse` metadata shape was deliberately preserved
  after regression caught an attempted additive change.
- Impala backend now reports real latency and wraps driver failures in safe
  `IMPALA_QUERY_FAILED` errors.

### Agent Studio and UI

- Five non-graph Agent Studio tools added under
  `projects/tempo_scan_impala/agent_studio_tools/`.
- PuppyGraph remains explicitly deferred.
- Ask AI shows Q4 capabilities and real-data examples only when OSSIE mode is
  enabled.
- Dashboard reuses the existing component shell but switches to Gross Sales,
  Fill Rate, Material, Sales Office, and Sell-In/Sell-Out context for the
  Impala profile.
- Forecast, weather, and market claims are hidden in the real-data profile.
- Legacy synthetic Dashboard and Ask AI behavior remain unchanged by default.

### Validation evidence

- Backend full suite: **376 passed**, 2 dependency deprecation warnings.
- Frontend full suite: **56 passed**.
- Frontend TypeScript: **no errors**.
- Linter diagnostics for changed files: **none**.
- Official OSSIE validation: **PASS**.
- Live Impala acceptance script:
  `scripts/validate_tempo_impala_live.py`.
- CAI deployment/rollback runbook:
  `docs/tempo-impala-ossie-runbook.md`.

### Still requires the CAI environment

- Upload and validate the five Agent Studio tools in Tools Playground.
- Collect 30–50 real TEMPO management questions.
- Obtain business approval for candidate metrics.

---

## Live Impala cutover + resolver fixes + legacy cleanup (24 Sep 2026)

Real-data cutover happened this session, superseding the "still requires the CAI environment" list above.

**Live Impala connectivity**: connected `tempo-backend` to the real CDP Impala Virtual Warehouse (LDAP/workload password, HTTP transport over port 443/`cliservice`, not the binary Thrift default). Added `impala_use_http_transport`/`impala_http_path` settings. Credentials live only in the CAI Application's Environment Variables UI, never committed.

**Root-caused and fixed a "5 files never committed" bug**: `dashboard.py`, `graph/{nodes,state,workflow}.py`, `core/schemas.py` had been edited in an earlier session but never `git add`ed (they were tracked-modified "M", not untracked "??", so a prior `git add <new-dir>` silently skipped them). This broke both Dashboard and Ask AI in OSSIE mode simultaneously. Found via a new `/api/debug/settings` diagnostic endpoint (`backend/app/api/routes/health.py`) that distinguishes "wrong config" from "stale/incomplete deployment" — same technique used in an earlier vLLM debugging session.

**Fixed a 10x baseline error** in `scripts/validate_tempo_impala_live.py`'s `EXPECTED_Q4_GROSS_SALES` constant (transcription error, not a data bug — the Gold-layer `×100` scaling chain was independently verified correct via `datasets/audit/*.sql`).

**Fixed two real bugs in `TempoOssieRegistry.resolve_metric()`** (`backend/app/ossie/registry.py`), found via a 5-question manual audit comparing a Python audit script's output against live Ask AI:
1. Word-order-sensitive exact-substring matching meant "nilai Sell-In terbesar" didn't match a synonym written as "material sell-in value" even though every content word was present. Fixed by adding token-overlap matching as a second, lower-priority match mode (substring matches still always outrank token-only matches).
2. "Fill Rate per bulan?" resolved to a granular per-material metric instead of the company-wide aggregate, because `company_fill_rate` had no bare "fill rate" synonym. Fixed by adding the synonym plus a scoring bonus for aggregate metrics when no other dimension qualifier is present.

**Delivered the exact user-specified greeting spec** (`backend/app/ossie/graph_nodes.py`'s `ossie_conversational`): shown once per session (gated on `state["history"]` being empty), with the 4 fixed example questions, then a short reply on later turns.

**Removed the legacy semantic layer from the live request path** (this was scoped down through discussion — see below):
- Deleted from `backend/app/graph/nodes.py`: `resolve_semantics`, `metric_unavailable`, `normalize_intent`, `generate_sql`, `repair_sql`, `validate_sql`, `execute_sql`, `result_checker`, `analyze_result`, `visualization_planner`, `ui_action_generator`, `direct_chat`, and the legacy keyword-routing tail of `route_intent` (now just greeting-vs-analytical → `ossie_conversational`/`ossie_analytical`).
- `backend/app/graph/workflow.py` rewired to only register `input_guard → route_intent → {ossie_analytical, ossie_conversational} → output_guard`, plus `fallback`.
- `backend/app/services/dashboard.py`: `get_dashboard_overview()` now calls the OSSIE path unconditionally; ~130 lines of legacy dashboard-query-building code deleted (`_load_dashboard_config`, `_validated_filters`, `_period_for`, `_build_query`, `_rows`).
- **Explicitly NOT deleted** (still used by the retained forecast/weather/market): `app/semantic/{loader,models}.py`, `projects/tempo_scan/semantic/*.yaml`. `app/semantic/{intent,resolver}.py` and `app/tools/{semantic_sql,chart_builder}.py` also stay, because `app/bootstrap/validation.py` (a separate synthetic-data-loading/validation harness, not part of the live request path) still imports them — out of scope for this cleanup, flagged but not touched.
- Deleted 4 test files that exercised only the removed legacy pipeline (`test_nl_to_sql.py`, `test_shared_context.py`, `test_shared_context_integration.py`, `test_query_service.py`); updated ~10 more that assumed legacy-mode defaults or routing.

**Made language detection more robust** (`backend/app/ossie/graph_nodes.py`'s `_language()`): added the `langdetect` library as a fallback for longer, keyword-less questions, keeping the existing exact-phrase greeting check first (langdetect is unreliable on 1-3 word inputs like "Halo"/"Hi" — verified empirically before deciding this). This replaces an ever-growing manual keyword list with real language identification for anything past a greeting.

**Config defaults changed** (`backend/app/core/config.py`, `.env.example`): `project_id` → `"tempo_scan_impala"`, `semantic_execution_mode` → `"ossie"`, `data_backend` → `"impala"`. Added `legacy_synthetic_project_id` (`"tempo_scan"`) so forecast/weather/market keep resolving their synthetic project explicitly rather than following `project_id` if it changes again.

**Validation**: backend full suite 337 passed (was 376 before the legacy-test deletions — the delta is entirely removed dead-code tests, not lost coverage of anything still reachable). Offline OSSIE/Impala contract validation: PASS.

**Explicitly out of scope this session** (per user's own scoping decisions, to revisit separately):
- Whether/how to retarget `forecasting/` to Impala (needs a new Gold-layer forecast table) vs. keep it on synthetic DuckDB.
- Whether `market_intelligence/`'s data (currently unfilled/unvalidated synthetic SerpAPI/Serper skeleton data) is worth keeping or filling.
- The planned new Agent Studio workflow connected to LiteLLM routing (mentioned once, not started).

---

## Milestone checklist

Reconstructed against the CAI/vLLM/Trino milestone framing from the ChatGPT-side plan (M-numbers approximate — align exact numbering with ChatGPT's own doc).

**Done**
- [x] M?: Qwen model deployed to CAI as its own Application, serving OpenAI-compatible `/v1/chat/completions`
- [x] M?: Qwen model registered in Agent Studio (full model path + explicit `https://` API Base — fixed earlier in the project)
- [x] M7.2: Split CAI Deployment — FE CAI App (tempo-frontend), BE CAI App (tempo-backend), Qwen CAI App (qwen-38-awq/vLLM) all live as separate Applications
- [x] Backend orchestration (LangGraph), semantic/governance layer, conversation memory (custom SQLite store), guardrails auto-install — all built and working on top of the split deployment
- [x] Agent Studio + vLLM compatibility bug (`System message must be at the beginning`) — root-caused and fixed (see incident summary above)
- [x] ~50-scenario manual test pass across greeting/analytical/forecast/guardrail/etc — used to drive a long list of correctness fixes (metric fabrication, language fallback, table-column bleed, missing caveats, guardrail bypass)
- [x] UX cleanup: floating AI drawer removed, Ask AI is the single chat surface, dashboard state still updates from it
- [x] Voice/visual polish: warmer consistent tone, no em dashes, custom "S" monogram icon, dashboard title removed, trend chart split with a metrics panel, custom font (Plus Jakarta Sans)
- [x] TEMPO Impala semantic data audit: 5 business-facing semantic views, 28-metric governed catalog, lineage/provenance, precision and grain validation
- [x] Additive Apache Ossie profile: official-schema model, governance, 31 golden questions, deterministic backend runtime, five Agent Studio tools, and default-off frontend profile
- [x] Foundation regression after OSSIE integration: backend 376 passed, frontend 56 passed, TypeScript clean
- [x] Live CAI Impala/Ossie connectivity and cutover — Impala credentials configured in CAI, live validation passing, `PROJECT_ID=tempo_scan_impala`/`DATA_BACKEND=impala`/`SEMANTIC_EXECUTION_MODE=ossie` are now the code defaults (not just env overrides)
- [x] Legacy DuckDB-synthetic semantic layer removed from the live Ask AI/Dashboard request path (see "Live Impala cutover + resolver fixes + legacy cleanup" above)

**Not started**
- [ ] Original M5.6/M8 Trino synthetic foundation remains unstarted and is no longer the immediate real-data path; the new Impala/Ossie profile is the current priority.
- [ ] LiteLLM Application confirmed end-to-end with a real Agent Studio workflow behind the `agent-studio-workflow` model group (it's deployed but that group is currently just a fallback placeholder, never exercised against a live workflow)
- [ ] Guardrails Hub validators (`DetectJailbreak`, `SecretsPresent`) confirmed installed and active in a real CAI Application run with `GUARDRAILS_ENABLED=true` (automated into startup, but the install step itself was never verified from outside a network-restricted sandbox)
- [ ] Revisit the "one bundled Application vs. 3-4 split Applications" tradeoff — user noted split deployment is what got built, but had separately said one bundled process is easier to troubleshoot; not reconciled against the M7.2 plan in this session
- [ ] forecasting/market_intelligence Impala retargeting decision (explicitly deferred, see above)
- [ ] Planned new Agent Studio workflow connected to LiteLLM routing (mentioned once, not started)

---

## Known state / not yet done

- **Default deployment is now Impala/OSSIE real data.** The old DuckDB-synthetic Ask AI/Dashboard path was removed from the live request path this session (24 Sep 2026); `tempo_scan`'s synthetic data and semantic YAML remain on disk only for forecast/weather/market intelligence and the standalone `app/bootstrap/` loader, not for Ask AI. The older Trino synthetic foundation remains unstarted and is not the immediate cutover path.
- Per the screenshot shared this session, the user's current milestone framing (from the ChatGPT-side plan) is:
  - **M7.2 Split CAI Deployment**: FE CAI App, BE CAI App, existing Qwen CAI App. This matches what's actually deployed (3 apps, or 4 with the optional LiteLLM layer).
  - Then **M5.6 / M8: Live Trino Data Foundation**: determine catalog/schema, create tables, populate synthetic sales/weather/market-intelligence/forecast data, validate golden queries, switch backend `DATA_BACKEND=trino`.
  - User's own stated preference (from the screenshot): bundling the 3 processes into one Application is "jauh lebih enak buat troubleshooting" than 3 separate ones. Worth surfacing back to ChatGPT as input to the plan, since the actual deployment ended up as 3-4 *separate* CAI Applications instead, for reasons never fully reconciled against that stated preference in this session.
- Agent Studio model registration (Qwen path) was fixed earlier in this project's history (full model path + explicit `https://` in API Base) and is marked working, separate from the later vLLM Application bug described above.
- LiteLLM Application is deployed but optional/default-off, not confirmed end-to-end with a live Agent Studio workflow behind it (the `agent-studio-workflow` model group is currently a fallback-to-`commercial-intelligence` placeholder).
- Guardrails Hub validator installation was authenticated and automated into CAI startup, but was never verified working end-to-end from outside the sandbox environment used mid-project (network restriction blocked verifying the install step directly). Needs a real check with `GUARDRAILS_ENABLED=true` set.

---

## Reference paths

- Backend entrypoint: `backend/app_cai_backend.py`, orchestration in `backend/app/graph/`
- Frontend: `frontend/src/views/{DashboardPage,AskAIPage}.tsx`, shared state in `frontend/src/lib/dashboardState.tsx`
- vLLM Application (the one with the glob bug, now fixed): `testing/model/vllm/{app.py,proxy.py}`
- Trusted reference vLLM setup (different model, Qwen3.5-9B, used as a pattern reference during the debugging session): `account/data intelligence/vllm/`
- LiteLLM: `litellm/{app_cai_litellm.py,config.yaml}`
- Governed OSSIE model/config (the live Ask AI path): `projects/tempo_scan_impala/ossie/{tempo_core.ossie.yaml,tempo_governance.yaml,golden_questions.yaml}`
- OSSIE backend runtime: `backend/app/ossie/{registry,service,graph_nodes}.py`
- Legacy synthetic project (now only used by forecast/weather/market, kept intact but disconnected from routing): `projects/tempo_scan/semantic/*.yaml`, `backend/app/forecasting/`, `backend/app/external_signals/weather/`, `backend/app/market_intelligence/`
- Standalone synthetic-data bootstrap/validation harness (separate from the live request path, untouched by the OSSIE cleanup): `backend/app/bootstrap/`
- Audited Impala semantic DDL/catalog: `datasets/audit/`
- CAI runbook: `docs/tempo-impala-ossie-runbook.md`
- Diagnostic endpoint for "is this a stale process or a bad config value": `GET /api/debug/settings` (`backend/app/api/routes/health.py`)
