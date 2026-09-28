-- Semantic Material 360 view.
-- Monetary fields use DECIMAL(38,2); ratios use DECIMAL(18,6).

CREATE VIEW gold.rpt_sap_material_month_semantic AS
SELECT
  calmonth,
  material,

  CAST(ROUND(bill_val, 2) AS DECIMAL(38,2))
    AS sell_in_bill_val,

  bill_qty AS sell_in_bill_qty,
  do_qty AS sales_do_qty,

  CAST(ROUND(do_amt, 2) AS DECIMAL(38,2))
    AS sales_do_amt,

  tot_stck AS warehouse_stock_qty,

  CAST(ROUND(val_stck, 2) AS DECIMAL(38,2))
    AS warehouse_stock_val,

  svc_do_qty AS service_do_qty,
  svc_po_qty AS service_po_qty,

  CAST(ROUND(svc_fill_rate, 6) AS DECIMAL(18,6))
    AS service_fill_rate,

  kode_plu AS retail_plu,

  CAST(ROUND(b2b_bill_val, 2) AS DECIMAL(38,2))
    AS sell_out_bill_val,

  b2b_bill_qty AS sell_out_bill_qty,

  has_sales AS has_sell_in,
  has_stock,
  has_service AS has_service_level,
  has_b2b AS has_sell_out,

  CAST(ROUND(bill_qty_per_stock_unit, 6) AS DECIMAL(18,6))
    AS sell_in_qty_per_stock_unit,

  CAST(ROUND(svc_do_to_sales_bill_qty, 6) AS DECIMAL(18,6))
    AS service_do_to_sell_in_bill_qty_ratio,

  CAST(ROUND(svc_do_to_sales_do_qty, 6) AS DECIMAL(18,6))
    AS service_do_to_sales_do_qty_ratio,

  CAST(ROUND(sales_to_b2b_val_ratio, 6) AS DECIMAL(18,6))
    AS sell_in_to_sell_out_value_ratio,

  CASE
    WHEN bill_val > 0
    THEN CAST(
      ROUND(b2b_bill_val / bill_val, 6)
      AS DECIMAL(18,6)
    )
  END AS sell_out_to_sell_in_value_ratio,

  CAST(ROUND(do_amt_to_bill_val_ratio, 6) AS DECIMAL(18,6))
    AS sales_do_amt_to_bill_val_ratio

FROM gold.rpt_sap_material_month;

-- Expected grain: one row per calmonth + material.
-- Use has_* flags before cross-domain analysis.
