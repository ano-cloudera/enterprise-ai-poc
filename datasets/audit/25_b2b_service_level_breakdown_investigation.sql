-- Step 1 of 2: column-name discovery for B2B and Service Level breakdown
-- expansion, requested 2026-09-28 as a follow-up to the Sales/Sell-In
-- customer+sales_office expansion (see
-- datasets/audit/24_sales_customer_office_breakdown_investigation.sql).
--
-- Audit findings before writing any CREATE VIEW:
--   - B2B: TEMPO_B2B_FIELD_CATALOG.md's grain note says the source row is
--     "customer x material x sales office x bulan" (+ branch/e-store/KA/
--     PLU) - all three requested dimensions already coexist on one row.
--     The current gold views (corr_b2b_branch_estore_month,
--     corr_b2b_material_plu) each pre-aggregate away some of them, so
--     neither alone supports a customer+material+sales_off breakdown.
--   - Service Level: TEMPO_SERVICE_LEVEL_FIELD_CATALOG.md's grain note
--     says "material x sales office x customer group (0CUST_GRP3) x
--     bulan". This is a customer GROUP (segmentation), not the individual
--     0CUSTOMER used by Sales/B2B - the same document says explicitly
--     these do not map 1:1 without a lookup. Do not conflate this new
--     dimension with Sales/B2B's "customer".
--   - Stock SAT-IDM: explicitly ruled out. TEMPO_STOCK_SAT_IDM_FIELD_
--     CATALOG.md states "Tidak ada customer/store di SAT-IDM" - it is a
--     DC/store stock snapshot, not a per-customer/sales_office
--     transaction feed. No expansion possible here without a new data
--     source.
--   - SAT OOS: already has cust_id/cust_code as dimensions
--     (gold.rpt_sat_oos_material_month) - no gap, no action needed.
--
-- This script only discovers exact column names (DESCRIBE) and checks
-- cardinality/nulls - it does not create any view. Write the CREATE VIEW
-- DDL only after confirming the real column names here; do not guess them
-- from the SAP InfoObject names in the field catalogs, which are not
-- always the literal silver column name (see c_0cust_grp3 vs 0CUST_GRP3,
-- t_group vs ..._GROUP, confirmed in-session from an actual DESCRIBE).
--
-- Run every block in Cloudera Workbench.

DESCRIBE silver.b2b_oct_dec_2024;
DESCRIBE silver.service_level_oct_dec_2024;

-- 1. B2B: cardinality/null-rate check for customer, sales_off, material
--    together on the same source row (not yet confirmed to coexist
--    cleanly on every row - the field catalog's grain note is a summary,
--    not a per-row guarantee).
-- NOTE: column names below (c_0sales_off, c_0branch, c_0e_store) are
-- guesses by analogy with silver.sales_oct_dec_2024's confirmed
-- c_0sales_off - verify against the DESCRIBE output above and correct
-- before running.
SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT c_0calmonth) AS distinct_calmonths,
  COUNT(DISTINCT c_0material) AS distinct_materials,
  COUNT(DISTINCT c_0customer) AS distinct_customers,
  COUNT(DISTINCT c_0sales_off) AS distinct_sales_offices,
  SUM(CASE WHEN c_0customer IS NULL OR TRIM(CAST(c_0customer AS STRING)) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_customer,
  SUM(CASE WHEN c_0sales_off IS NULL OR TRIM(CAST(c_0sales_off AS STRING)) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_sales_off
FROM silver.b2b_oct_dec_2024
WHERE c_0calmonth IS NOT NULL AND c_0material IS NOT NULL;

-- 2. B2B candidate grain: calmonth + material + customer + sales_off, all
--    four together. Compare row_count here against corr_b2b_material_plu's
--    existing row count for the same period as a sanity check.
SELECT
  c_0calmonth AS calmonth,
  c_0material AS material,
  c_0customer AS customer,
  c_0sales_off AS sales_off,
  SUM(bill_val) AS b2b_bill_val,
  SUM(c_0bill_qty) AS b2b_bill_qty,
  COUNT(*) AS source_rows
FROM silver.b2b_oct_dec_2024
WHERE c_0calmonth IS NOT NULL
  AND c_0material IS NOT NULL
  AND c_0customer IS NOT NULL
  AND c_0sales_off IS NOT NULL
GROUP BY c_0calmonth, c_0material, c_0customer, c_0sales_off
ORDER BY b2b_bill_val DESC
LIMIT 20;

-- 3. Service Level: cardinality/null-rate check for sales_off and
--    cust_grp3 alongside the existing calmonth+material grain.
-- NOTE: column names below (c_0sales_off, c_0cust_grp3) are guesses by
-- analogy - verify against the DESCRIBE output above and correct before
-- running.
SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT c_0calmonth) AS distinct_calmonths,
  COUNT(DISTINCT c_0material) AS distinct_materials,
  COUNT(DISTINCT c_0sales_off) AS distinct_sales_offices,
  COUNT(DISTINCT c_0cust_grp3) AS distinct_customer_groups,
  SUM(CASE WHEN c_0sales_off IS NULL OR TRIM(CAST(c_0sales_off AS STRING)) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_sales_off,
  SUM(CASE WHEN c_0cust_grp3 IS NULL OR TRIM(CAST(c_0cust_grp3 AS STRING)) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_cust_grp3
FROM silver.service_level_oct_dec_2024
WHERE c_0calmonth IS NOT NULL AND c_0material IS NOT NULL;

-- 4. Service Level candidate grain: calmonth + material + sales_off +
--    cust_grp3.
SELECT
  c_0calmonth AS calmonth,
  c_0material AS material,
  c_0sales_off AS sales_off,
  c_0cust_grp3 AS cust_grp3,
  SUM(do_qty) AS service_do_qty,
  SUM(po_qty) AS service_po_qty,
  CASE WHEN SUM(po_qty) > 0 THEN SUM(do_qty) / SUM(po_qty) END AS fill_rate,
  COUNT(*) AS source_rows
FROM silver.service_level_oct_dec_2024
WHERE c_0calmonth IS NOT NULL
  AND c_0material IS NOT NULL
  AND c_0sales_off IS NOT NULL
  AND c_0cust_grp3 IS NOT NULL
GROUP BY c_0calmonth, c_0material, c_0sales_off, c_0cust_grp3
ORDER BY service_do_qty DESC
LIMIT 20;

-- 5. Reconciliation sanity checks against existing governed totals for
--    the same period - a material mismatch means a double-count or filter
--    difference and the new view must not be deployed until understood.
SELECT
  c_0calmonth AS calmonth,
  SUM(bill_val) AS b2b_bill_val_via_rollup
FROM silver.b2b_oct_dec_2024
WHERE c_0calmonth IS NOT NULL AND c_0customer IS NOT NULL AND c_0sales_off IS NOT NULL
GROUP BY c_0calmonth
ORDER BY calmonth;

SELECT calmonth, b2b_bill_val
FROM gold.rpt_sap_monthly_executive_semantic
ORDER BY calmonth;

SELECT
  c_0calmonth AS calmonth,
  SUM(do_qty) AS service_do_qty_via_rollup,
  SUM(po_qty) AS service_po_qty_via_rollup
FROM silver.service_level_oct_dec_2024
WHERE c_0calmonth IS NOT NULL AND c_0sales_off IS NOT NULL AND c_0cust_grp3 IS NOT NULL
GROUP BY c_0calmonth
ORDER BY calmonth;

SELECT calmonth, svc_do_qty, svc_po_qty
FROM gold.rpt_sap_monthly_executive_semantic
ORDER BY calmonth;
