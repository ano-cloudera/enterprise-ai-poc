-- Semantic presentation wrapper for stable financial precision.
-- Upstream business view remains unchanged for backward compatibility.

CREATE VIEW gold.rpt_sap_monthly_executive_semantic AS
SELECT
  calmonth,

  CAST(ROUND(sales_bill_val, 2) AS DECIMAL(38,2))
    AS sales_bill_val,

  sales_bill_qty,
  sales_do_qty,

  CAST(ROUND(sales_do_amt, 2) AS DECIMAL(38,2))
    AS sales_do_amt,

  sales_materials,
  sales_customers,

  stock_qty,

  CAST(ROUND(stock_val, 2) AS DECIMAL(38,2))
    AS stock_val,

  stock_materials,
  svc_do_qty,
  svc_po_qty,

  CAST(ROUND(svc_fill_rate, 6) AS DECIMAL(18,6))
    AS svc_fill_rate,

  svc_materials,

  CAST(ROUND(b2b_bill_val, 2) AS DECIMAL(38,2))
    AS b2b_bill_val,

  b2b_bill_qty,
  b2b_materials,
  b2b_customers,

  CAST(ROUND(do_amt_to_bill_val_ratio, 6) AS DECIMAL(18,6))
    AS do_amt_to_bill_val_ratio,

  CAST(ROUND(stock_to_sales_bill_qty_ratio, 6) AS DECIMAL(18,6))
    AS stock_to_sales_bill_qty_ratio

FROM gold.rpt_sap_monthly_executive;

-- Expected grain: one row per calmonth.
-- Monetary columns: DECIMAL(38,2).
-- Ratio columns: DECIMAL(18,6).
