-- Showcase admission audit for Gold views that exist in the TEMPO environment
-- but are not yet part of the OSSIE runtime contract.
--
-- Run this in Impala before admitting a view. A view name in an inventory or
-- Irvan's reference catalog is not sufficient evidence of physical columns,
-- grain, or safe aggregation behavior.

-- 1. Capture the physical contracts first.
DESCRIBE gold.corr_sales_material_total;
DESCRIBE gold.corr_sales_customer_month;
DESCRIBE gold.corr_sales_sales_office;
DESCRIBE gold.corr_picking_sales_office;
DESCRIBE gold.rpt_picking_status_summary;
DESCRIBE gold.corr_unloading_sales_office;
DESCRIBE gold.corr_sat_promo_materials;

-- 2. Views whose schemas are already evidenced by repository DDL.
-- Expected grain: one row per calmonth + customer.
SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT CONCAT(CAST(calmonth AS STRING), '|', CAST(customer AS STRING)))
    AS distinct_grain,
  SUM(CASE WHEN calmonth IS NULL OR customer IS NULL THEN 1 ELSE 0 END)
    AS null_grain_rows
FROM gold.corr_sales_customer_month;

-- Expected grain: one row per sales_off. BILL_VAL is value, SALES_LINES is a
-- row count; this view currently has no evidenced BILL_QTY column.
SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT sales_off) AS distinct_grain,
  SUM(CASE WHEN sales_off IS NULL THEN 1 ELSE 0 END) AS null_grain_rows,
  SUM(CASE WHEN sales_lines < 0 THEN 1 ELSE 0 END) AS invalid_sales_lines
FROM gold.corr_sales_sales_office;

-- Expected grain: one row per sales_off. Delay rate must remain within 0..1.
SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT sales_off) AS distinct_grain,
  SUM(CASE WHEN sales_off IS NULL THEN 1 ELSE 0 END) AS null_grain_rows,
  SUM(CASE WHEN delay_rate < 0 OR delay_rate > 1 THEN 1 ELSE 0 END)
    AS invalid_delay_rate,
  SUM(CASE WHEN pick_rows < 0 THEN 1 ELSE 0 END) AS invalid_pick_rows
FROM gold.corr_picking_sales_office;

-- Expected grain: one row per sales_off. UNLOAD_ROWS is an event-row count,
-- not quantity unloaded or a distinct-document count.
SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT sales_off) AS distinct_grain,
  SUM(CASE WHEN sales_off IS NULL THEN 1 ELSE 0 END) AS null_grain_rows,
  SUM(CASE WHEN unload_rows < 0 THEN 1 ELSE 0 END) AS invalid_unload_rows
FROM gold.corr_unloading_sales_office;

-- 3. Stop here for the following views until DESCRIBE output is recorded:
--   gold.corr_sales_material_total
--   gold.rpt_picking_status_summary
--   gold.corr_sat_promo_materials
-- Their names appear in the supplied inventory/reference catalog, but this
-- repository does not contain authoritative CREATE VIEW definitions for
-- them. Do not infer columns or grain from names, and do not add them to OSSIE
-- until row-count, distinct-grain, null, enum, and denominator checks pass.
