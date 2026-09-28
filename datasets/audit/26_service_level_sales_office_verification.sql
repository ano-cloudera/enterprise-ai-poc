-- Post-create verification for gold.corr_service_sales_office_material_month
-- (see datasets/gold/26_rpt_service_level_sales_office_semantic.sql for the
-- CREATE VIEW and the reasoning for excluding c_0cust_grp3/c_0af_cgr6).
--
-- Run each statement individually in Workbench (highlight one full
-- statement at a time, not the whole file) - a prior session found that
-- running multiple CREATE VIEW/SELECT statements as one highlighted block
-- can throw a ParseException.

DESCRIBE gold.corr_service_sales_office_material_month;

-- Duplicate-grain check - expect 0.
SELECT COUNT(*) AS duplicate_grain_rows
FROM (
  SELECT calmonth, material, sales_off, COUNT(*) AS grain_rows
  FROM gold.corr_service_sales_office_material_month
  GROUP BY calmonth, material, sales_off
  HAVING COUNT(*) > 1
) duplicate_grains;

-- Reconciliation against the existing governed monthly total
-- (monthly_executive.svc_do_qty/svc_po_qty) - should match exactly per
-- calmonth (modulo float rounding noise, same pattern already confirmed
-- for the Sales and B2B expansions).
SELECT calmonth, SUM(service_do_qty) AS service_do_qty_via_sales_office, SUM(service_po_qty) AS service_po_qty_via_sales_office
FROM gold.corr_service_sales_office_material_month
GROUP BY calmonth
ORDER BY calmonth;

SELECT calmonth, svc_do_qty, svc_po_qty
FROM gold.rpt_sap_monthly_executive_semantic
ORDER BY calmonth;
