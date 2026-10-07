-- Investigate: material_360 sell-out = 0 with has_sell_out = TRUE
-- Run on Impala (gold). Expected: semantic sell_out_bill_val matches corr + silver rollup.

-- 1) Semantic wrapper fidelity (from 11_semantic_views_final_audit.sql)
SELECT
  MAX(ABS(CAST(semantic.sell_out_bill_val AS DOUBLE) - ROUND(raw.b2b_bill_val, 2)))
    AS max_sell_out_rounding_diff
FROM gold.rpt_sap_material_month raw
JOIN gold.rpt_sap_material_month_semantic semantic
  ON raw.calmonth = semantic.calmonth AND raw.material = semantic.material;

-- 2) Coverage: how many B2B-scoped rows are literally zero billing?
SELECT
  COUNT(*) AS material_month_rows,
  SUM(CASE WHEN has_sell_out THEN 1 ELSE 0 END) AS has_sell_out_rows,
  SUM(CASE WHEN has_sell_out AND sell_out_bill_val = 0 THEN 1 ELSE 0 END) AS has_flag_val_zero,
  SUM(CASE WHEN has_sell_out AND sell_out_bill_val > 0 THEN 1 ELSE 0 END) AS has_flag_val_pos
FROM gold.rpt_sap_material_month_semantic
WHERE calmonth BETWEEN 202410 AND 202412;

-- 3) Reconcile semantic material sell-out to governed corr rollup (should match per material-month)
SELECT
  COUNT(*) AS joined_rows,
  SUM(CASE WHEN ABS(COALESCE(m.sell_out_bill_val, 0) - COALESCE(c.bill_val, 0)) > 0.01 THEN 1 ELSE 0 END)
    AS mismatched_rows
FROM gold.rpt_sap_material_month_semantic m
FULL OUTER JOIN gold.corr_b2b_material_month c
  ON m.calmonth = c.calmonth AND m.material = c.material
WHERE COALESCE(m.calmonth, c.calmonth) BETWEEN 202410 AND 202412;

-- 4) Company total: semantic vs corr (should match executive B2B month totals)
SELECT 'semantic' AS src, SUM(sell_out_bill_val) AS q4_b2b_val
FROM gold.rpt_sap_material_month_semantic
WHERE calmonth BETWEEN 202410 AND 202412
UNION ALL
SELECT 'corr_b2b_material_month', SUM(bill_val)
FROM gold.corr_b2b_material_month
WHERE calmonth BETWEEN 202410 AND 202412;

-- 5) Sample materials from Ask AI "top terendah" (replace list as needed)
SELECT
  m.material,
  SUM(m.sell_out_bill_val) AS semantic_q4,
  SUM(c.bill_val) AS corr_q4,
  SUM(s.bill_val) AS silver_q4,
  SUM(s.c_0bill_qty) AS silver_qty
FROM gold.rpt_sap_material_month_semantic m
LEFT JOIN gold.corr_b2b_material_month c
  ON m.calmonth = c.calmonth AND m.material = c.material
LEFT JOIN (
  SELECT c_0calmonth AS calmonth, c_0material AS material,
         SUM(bill_val) AS bill_val, SUM(c_0bill_qty) AS c_0bill_qty
  FROM silver.b2b_oct_dec_2024
  WHERE c_0calmonth BETWEEN 202410 AND 202412
  GROUP BY c_0calmonth, c_0material
) s ON m.calmonth = s.calmonth AND m.material = s.material
WHERE m.calmonth BETWEEN 202410 AND 202412
  AND m.material IN ('035-37-01', '076-07-00', '908-40-01', '005-15-02', '500-11-04')
GROUP BY m.material;

-- 6) If silver shows bill_val > 0 but semantic = 0 → view/join bug.
-- If silver also 0 but has_sell_out TRUE → flag means "in B2B universe", not "has billing".
