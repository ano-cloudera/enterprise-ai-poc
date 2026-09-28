-- Semantic Service Level material-month view.
-- Upstream fill_rate_band includes an explicit unknown category.

CREATE VIEW gold.rpt_service_level_material_month_semantic AS
SELECT
  calmonth,
  material,

  do_qty AS service_do_qty,
  po_qty AS service_po_qty,

  CAST(ROUND(fill_rate, 6) AS DECIMAL(18,6))
    AS service_fill_rate,

  fill_rate_band,

  sales_bill_qty AS sell_in_bill_qty,

  CAST(ROUND(sales_bill_val, 2) AS DECIMAL(38,2))
    AS sell_in_bill_val,

  tot_stck AS warehouse_stock_qty,

  TRUE AS has_service_level,
  sales_bill_qty IS NOT NULL AS has_sell_in,
  tot_stck IS NOT NULL AS has_stock,
  fill_rate IS NOT NULL AS has_fill_rate

FROM gold.rpt_service_level_material_month;

-- Expected grain: one row per calmonth + material.
