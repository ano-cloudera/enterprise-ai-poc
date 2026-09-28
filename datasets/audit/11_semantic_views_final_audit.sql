-- Final audit for the five TEMPO semantic source views.
-- Run before deploying 03_rpt_semantic_metric_catalog.sql.

-- ============================================================================
-- 1. Grain uniqueness (all queries must return 0 rows)
-- ============================================================================

SELECT calmonth, COUNT(*) AS row_count
FROM gold.rpt_sap_monthly_executive_semantic
GROUP BY calmonth
HAVING COUNT(*) > 1;

SELECT calmonth, material, COUNT(*) AS row_count
FROM gold.rpt_sap_material_month_semantic
GROUP BY calmonth, material
HAVING COUNT(*) > 1;

SELECT calmonth, material, COUNT(*) AS row_count
FROM gold.rpt_service_level_material_month_semantic
GROUP BY calmonth, material
HAVING COUNT(*) > 1;

SELECT calmonth, customer, COUNT(*) AS row_count
FROM gold.rpt_sap_customer_reconciliation_semantic
GROUP BY calmonth, customer
HAVING COUNT(*) > 1;

SELECT reporting_period, sales_office, COUNT(*) AS row_count
FROM gold.rpt_sales_office_performance_semantic
GROUP BY reporting_period, sales_office
HAVING COUNT(*) > 1;

-- ============================================================================
-- 2. Dataset shape and coverage
-- ============================================================================

SELECT
  'monthly_executive' AS dataset,
  COUNT(*) AS row_count,
  COUNT(DISTINCT calmonth) AS distinct_key_count
FROM gold.rpt_sap_monthly_executive_semantic

UNION ALL

SELECT
  'material_360',
  COUNT(*),
  COUNT(DISTINCT CONCAT(CAST(calmonth AS STRING), '|', material))
FROM gold.rpt_sap_material_month_semantic

UNION ALL

SELECT
  'service_level_material',
  COUNT(*),
  COUNT(DISTINCT CONCAT(CAST(calmonth AS STRING), '|', material))
FROM gold.rpt_service_level_material_month_semantic

UNION ALL

SELECT
  'customer_reconciliation',
  COUNT(*),
  COUNT(DISTINCT CONCAT(CAST(calmonth AS STRING), '|', customer))
FROM gold.rpt_sap_customer_reconciliation_semantic

UNION ALL

SELECT
  'sales_office_q4',
  COUNT(*),
  COUNT(DISTINCT CONCAT(reporting_period, '|', sales_office))
FROM gold.rpt_sales_office_performance_semantic;

-- Expected: row_count = distinct_key_count for every dataset.

-- ============================================================================
-- 3. Period scope
-- ============================================================================

SELECT
  MIN(calmonth) AS min_month,
  MAX(calmonth) AS max_month,
  COUNT(DISTINCT calmonth) AS reporting_months
FROM gold.rpt_sap_monthly_executive_semantic;

SELECT DISTINCT
  reporting_period,
  period_start_calmonth,
  period_end_calmonth,
  reporting_grain
FROM gold.rpt_sales_office_performance_semantic;

-- ============================================================================
-- 4. Fill-rate governance
-- ============================================================================

SELECT
  COUNT(*) AS invalid_fill_band_rows
FROM gold.rpt_service_level_material_month_semantic
WHERE
  (service_fill_rate IS NULL AND fill_rate_band <> 'unknown')
  OR (service_fill_rate < 0.5 AND fill_rate_band <> 'low_fill')
  OR (
    service_fill_rate >= 0.5
    AND service_fill_rate < 0.8
    AND fill_rate_band <> 'medium_fill'
  )
  OR (service_fill_rate >= 0.8 AND fill_rate_band <> 'high_fill');

-- Expected: 0.

-- ============================================================================
-- 5. Precision wrappers preserve business values
-- ============================================================================

SELECT
  MAX(
    ABS(
      CAST(semantic.sales_bill_val AS DOUBLE)
      - ROUND(raw.sales_bill_val, 2)
    )
  ) AS max_executive_sales_value_difference,
  MAX(
    ABS(
      CAST(semantic.svc_fill_rate AS DOUBLE)
      - ROUND(raw.svc_fill_rate, 6)
    )
  ) AS max_executive_fill_rate_difference
FROM gold.rpt_sap_monthly_executive raw
JOIN gold.rpt_sap_monthly_executive_semantic semantic
  ON raw.calmonth = semantic.calmonth;

SELECT
  MAX(
    ABS(
      CAST(semantic.sell_in_bill_val AS DOUBLE)
      - ROUND(raw.bill_val, 2)
    )
  ) AS max_material_sales_value_difference,
  MAX(
    ABS(
      CAST(semantic.sell_out_bill_val AS DOUBLE)
      - ROUND(raw.b2b_bill_val, 2)
    )
  ) AS max_material_sell_out_value_difference
FROM gold.rpt_sap_material_month raw
JOIN gold.rpt_sap_material_month_semantic semantic
  ON raw.calmonth = semantic.calmonth
 AND raw.material = semantic.material;

-- Expected differences: 0 or floating-point noise close to 0.

-- ============================================================================
-- 6. Coverage summaries
-- ============================================================================

SELECT
  COUNT(*) AS material_months,
  SUM(CASE WHEN has_sell_in THEN 1 ELSE 0 END) AS has_sell_in,
  SUM(CASE WHEN has_stock THEN 1 ELSE 0 END) AS has_stock,
  SUM(CASE WHEN has_service_level THEN 1 ELSE 0 END) AS has_service_level,
  SUM(CASE WHEN has_sell_out THEN 1 ELSE 0 END) AS has_sell_out
FROM gold.rpt_sap_material_month_semantic;

SELECT
  COUNT(*) AS customer_months,
  COUNT(DISTINCT customer) AS shared_customers,
  COUNT(DISTINCT calmonth) AS reporting_months
FROM gold.rpt_sap_customer_reconciliation_semantic;

SELECT
  COUNT(*) AS total_offices,
  SUM(CASE WHEN has_sell_in THEN 1 ELSE 0 END) AS has_sell_in,
  SUM(CASE WHEN has_picking THEN 1 ELSE 0 END) AS has_picking,
  SUM(CASE WHEN has_unloading THEN 1 ELSE 0 END) AS has_unloading,
  SUM(
    CASE
      WHEN has_sell_in AND has_picking AND has_unloading THEN 1
      ELSE 0
    END
  ) AS full_coverage
FROM gold.rpt_sales_office_performance_semantic;
