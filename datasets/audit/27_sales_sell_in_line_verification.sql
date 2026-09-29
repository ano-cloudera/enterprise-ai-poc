-- Post-create verification for gold.rpt_sales_sell_in_line_semantic (see
-- datasets/gold/27_rpt_sales_sell_in_line_semantic.sql for the CREATE VIEW
-- and reasoning). Run each statement individually in Workbench - a prior
-- session found that running multiple CREATE VIEW/SELECT statements as one
-- highlighted block can throw a ParseException.

DESCRIBE gold.rpt_sales_sell_in_line_semantic;

-- Row count sanity check - should be very close to (ideally identical to)
-- the source silver table's row count for rows with a non-null calmonth
-- and material.
SELECT COUNT(*) AS row_count
FROM gold.rpt_sales_sell_in_line_semantic;

SELECT COUNT(*) AS source_row_count
FROM silver.sales_oct_dec_2024
WHERE c_0calmonth IS NOT NULL AND material IS NOT NULL;

-- Reconciliation: SUM(sell_in_bill_val), rolled up to calmonth only,
-- should match the existing governed monthly gross_billing_value total
-- exactly (modulo float/DECIMAL(38,2) trailing-digit noise, same pattern
-- already confirmed for the Sales/B2B/Service Level expansions this
-- session).
SELECT calmonth, SUM(sell_in_bill_val) AS sell_in_bill_val_via_line
FROM gold.rpt_sales_sell_in_line_semantic
GROUP BY calmonth
ORDER BY calmonth;

SELECT calmonth, sales_bill_val
FROM gold.rpt_sap_monthly_executive_semantic
ORDER BY calmonth;

-- Spot-check the new dimensions this view adds beyond the existing
-- material_360/customer_material_360/sales_office_material_360 views:
-- sales_grp, cust_grp3, material_group. Confirms these columns are
-- populated (not entirely null) and gives a first look at their
-- cardinality before anyone builds a dashboard filter on them.
SELECT
  COUNT(DISTINCT sales_grp) AS distinct_sales_grp,
  COUNT(DISTINCT cust_grp3) AS distinct_cust_grp3,
  COUNT(DISTINCT material_group) AS distinct_material_group,
  SUM(CASE WHEN sales_grp IS NULL THEN 1 ELSE 0 END) AS null_sales_grp,
  SUM(CASE WHEN cust_grp3 IS NULL THEN 1 ELSE 0 END) AS null_cust_grp3,
  SUM(CASE WHEN material_group IS NULL THEN 1 ELSE 0 END) AS null_material_group
FROM gold.rpt_sales_sell_in_line_semantic;
