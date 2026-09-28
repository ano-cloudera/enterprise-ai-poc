-- Investigate whether Sales/Sell-In can be broken down by customer and by
-- sales_office at the material+month grain, not just the coarser
-- customer-only (gold.corr_sales_customer_month) and sales_office-only-
-- for-all-of-Q4 (gold.corr_sales_sales_office) aggregates that already
-- exist. Requested 2026-09-28: Sales/Sell-In, B2B, Stock SAT-IDM, SAT OOS,
-- and Service Level all deserve customer/sales_office/group breakdowns, not
-- just material+month.
--
-- sales_office is being treated as a working assumption ("a branch in a
-- given region"), per TEMPO_SALES_FIELD_CATALOG.md's note that 0SALES_OFF
-- is "asumsi PoC, follow-up Tempo" - not yet a Tempo-confirmed business
-- definition. The resulting metric must carry that caveat, same as every
-- other approved_candidate/pending_business_confirmation metric already in
-- the semantic layer.
--
-- Run every block in Cloudera Workbench before deploying the gold views.

DESCRIBE silver.sales_oct_dec_2024;

-- 1. Cardinality and null-rate check for the two candidate dimensions at
--    the material+month grain, before committing to a view.
SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT c_0calmonth) AS distinct_calmonths,
  COUNT(DISTINCT material) AS distinct_materials,
  COUNT(DISTINCT c_0customer) AS distinct_customers,
  COUNT(DISTINCT c_0sales_off) AS distinct_sales_offices,
  SUM(CASE WHEN c_0customer IS NULL OR TRIM(CAST(c_0customer AS STRING)) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_customer,
  SUM(CASE WHEN c_0sales_off IS NULL OR TRIM(CAST(c_0sales_off AS STRING)) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_sales_off
FROM silver.sales_oct_dec_2024
WHERE c_0calmonth IS NOT NULL AND material IS NOT NULL;

-- 2. Candidate grain: calmonth + material + customer. More than one source
--    row per grain is expected (one customer buys the same material more
--    than once a month) - that is what SUM(bill_val) aggregates over.
SELECT
  c_0calmonth AS calmonth,
  material,
  c_0customer AS customer,
  SUM(bill_val) * 100 AS sell_in_bill_val,
  SUM(c_0bill_qty) AS sell_in_bill_qty,
  COUNT(*) AS source_rows
FROM silver.sales_oct_dec_2024
WHERE c_0calmonth IS NOT NULL
  AND material IS NOT NULL
  AND c_0customer IS NOT NULL
  AND TRIM(CAST(c_0customer AS STRING)) <> ''
GROUP BY c_0calmonth, material, c_0customer
ORDER BY sell_in_bill_val DESC
LIMIT 20;

-- 3. Candidate grain: calmonth + material + sales_office.
SELECT
  c_0calmonth AS calmonth,
  material,
  lpad(trim(CAST(c_0sales_off AS STRING)), 4, '0') AS sales_office,
  SUM(bill_val) * 100 AS sell_in_bill_val,
  SUM(c_0bill_qty) AS sell_in_bill_qty,
  COUNT(*) AS source_rows
FROM silver.sales_oct_dec_2024
WHERE c_0calmonth IS NOT NULL
  AND material IS NOT NULL
  AND c_0sales_off IS NOT NULL
  AND TRIM(CAST(c_0sales_off AS STRING)) <> ''
GROUP BY c_0calmonth, material, lpad(trim(CAST(c_0sales_off AS STRING)), 4, '0')
ORDER BY sell_in_bill_val DESC
LIMIT 20;

-- 4. Sanity check against the already-governed company-level total
--    (gross_billing_value, SI-01): SUM(sell_in_bill_val) grouped only by
--    calmonth from the new customer-grain and office-grain candidates
--    should reconcile to the same monthly total as
--    gold.rpt_sap_monthly_executive_semantic.sales_bill_val. A material
--    mismatch here means a double-count or a filter difference and the
--    view must not be deployed until it is understood.
SELECT
  c_0calmonth AS calmonth,
  SUM(bill_val) * 100 AS sell_in_bill_val_via_customer_rollup
FROM silver.sales_oct_dec_2024
WHERE c_0calmonth IS NOT NULL AND c_0customer IS NOT NULL AND TRIM(CAST(c_0customer AS STRING)) <> ''
GROUP BY c_0calmonth
ORDER BY calmonth;

SELECT calmonth, sales_bill_val
FROM gold.rpt_sap_monthly_executive_semantic
ORDER BY calmonth;

-- Post-create contract checks for the new semantic views (run after the
-- CREATE VIEW statements in datasets/gold/24_*.sql have been applied).
DESCRIBE gold.rpt_sap_customer_material_month_semantic;
DESCRIBE gold.rpt_sap_sales_office_material_month_semantic;

SELECT COUNT(*) AS duplicate_grain_rows
FROM (
  SELECT calmonth, material, customer, COUNT(*) AS grain_rows
  FROM gold.rpt_sap_customer_material_month_semantic
  GROUP BY calmonth, material, customer
  HAVING COUNT(*) > 1
) duplicate_grains;

SELECT COUNT(*) AS duplicate_grain_rows
FROM (
  SELECT calmonth, material, sales_office, COUNT(*) AS grain_rows
  FROM gold.rpt_sap_sales_office_material_month_semantic
  GROUP BY calmonth, material, sales_office
  HAVING COUNT(*) > 1
) duplicate_grains;
