# Agent Studio Nine-Domain Acceptance

**Date:** 28 September 2026
**Workflow:** Tempo-Scan-Intelligence-Prod
**Status:** Local contract and Workbench Gold gate verified; Agent Studio runtime rebuild, redeployment, and live UI/API evidence pending.

## Frozen local contract

- Datasets: 15
- Metrics: 50
- Golden questions: 75
- SAT Promo source: `gold.rpt_sat_promo_material_december_semantic`
- SAT Promo metrics: `PR-03` (`promo_observation_count`) and `PR-02` (`promo_material_count`)
- Raw status policy: report Y/X/T literally; do not infer active/inactive.

## Deployment gates

- [x] Run `datasets/audit/23_sat_promo_gold_contract.sql` in Workbench.
- [x] Append null, date-range, canonical-grain, and reconciliation outputs to `datasets/qa/23_sat_promo_gold_contract.md`.
- [x] Deploy `datasets/gold/23_rpt_sat_promo_material_december_semantic.sql`.
- [ ] Rebuild the Agent Studio runtime bundle and confirm it contains the 15-dataset/50-metric OSSIE files.
- [ ] Redeploy Tempo-Scan-Intelligence-Prod.

## Live acceptance matrix

| Domain | Prompt | Expected metric | UI | API | Trace ID | Latency | Result |
|---|---|---|---|---|---|---|---|
| Sales / Sell-In | Berapa GBV Q4 2024? | `gross_billing_value` | pending | pending | pending | pending | pending |
| B2B / Sell-Out | Berapa top 10 branch dengan B2B value tertinggi? | `b2b_branch_sell_out_value` | pending | pending | pending | pending | pending |
| Stock Tempo | Berapa stock value Tempo selama Q4 2024? | `stock_tempo_value` | pending | pending | pending | pending | pending |
| Stock SAT-IDM | DC mana dengan IDM stock terendah selama Q4 2024? | `sat_idm_dc_stock_quantity` | pending | pending | pending | pending | pending |
| SAT OOS | Material mana yang paling sering OOS selama Q4 2024? | `sat_oos_rate` | pending | pending | pending | pending | pending |
| Service Level | Material mana dengan unfulfilled quantity terbesar? | `service_unfulfilled_quantity` | pending | pending | pending | pending | pending |
| Picking | Sales office mana dengan picking workload tertinggi? | `picking_workload_rows` | pending | pending | pending | pending | pending |
| Unloading | Sales office mana dengan unloading events terbanyak? | `unloading_event_count` | pending | pending | pending | pending | pending |
| SAT Promo | Jumlah observasi promo per mekanisme Desember 2024 | `promo_observation_count` | pending | pending | pending | pending | pending |

## SAT Promo safety controls

| Prompt | Expected | UI | API | Result |
|---|---|---|---|---|
| Bagaimana distribusi kode program status Y/X/T? | Governed raw-code table plus caveat | pending | pending | pending |
| Berapa promo aktif Desember 2024? | Unsupported; status mapping unconfirmed | pending | pending | pending |
| Berapa revenue atau ROI dari promo? | Unsupported; cost/attribution unavailable | pending | pending | pending |
| Bagaimana tren promo Oktober sampai Desember 2024? | Unsupported; December-only source | pending | pending | pending |

Do not store API keys, Authorization headers, cookies, or credentials in this document.
