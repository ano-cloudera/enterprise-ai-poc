-- Registry of candidate metrics for Semantic Contract v2 (NOT published in v1 catalog).
-- Do not INSERT into gold.rpt_semantic_metric_catalog until business approval.
-- See projects/tempo_scan_impala/ossie/CANDIDATE_METRICS_V2.md

-- | metric_id | source_view | catalog_question_ids | promotion_gate |
-- | OOS-01-EXP | gold.rpt_sat_oos_month_exploratory | O01,O02 | UAT + 2 golden supported |
-- | PR-01-EXP | gold.rpt_promo_material_coverage_des | P01 | ETL promo Des deployed |
-- | PR-02-EXP | join promo + sales Des | PQ1 | audited join SQL |
-- | IDM-01-EXP | gold.rpt_stock_sat_idm_exploratory | I03,I05 | stg_stock_sat_idm loaded |
-- | SL-02-CAND | service_level_material | L05 gap | unfulfilled PO qty formula approved |

-- v1 remains 28 metrics in tempo_core.ossie.yaml until rows above are promoted.
