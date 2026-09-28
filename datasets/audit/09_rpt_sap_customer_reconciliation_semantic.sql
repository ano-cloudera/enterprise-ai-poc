-- Semantic customer reconciliation view.
-- Scope: customers present in both Sell-In and Sell-Out (INNER JOIN upstream).
-- Legacy sales_to_b2b_ratio is intentionally not exposed.

CREATE VIEW gold.rpt_sap_customer_reconciliation_semantic AS
SELECT
  calmonth,
  customer,

  CAST(ROUND(sales_bill_val, 2) AS DECIMAL(38,2))
    AS sell_in_bill_val,

  CAST(ROUND(b2b_bill_val, 2) AS DECIMAL(38,2))
    AS sell_out_bill_val,

  CAST(ROUND(bill_val_variance, 2) AS DECIMAL(38,2))
    AS sell_in_minus_sell_out_val,

  CAST(ROUND(sell_in_to_sell_out_ratio, 6) AS DECIMAL(18,6))
    AS sell_in_to_sell_out_value_ratio,

  CAST(ROUND(sell_out_to_sell_in_ratio, 6) AS DECIMAL(18,6))
    AS sell_out_to_sell_in_value_ratio,

  CAST(ROUND(bill_val_pct_variance, 6) AS DECIMAL(18,6))
    AS absolute_variance_rate_vs_sell_out,

  'shared_customer_only' AS reconciliation_scope,
  TRUE AS has_sell_in,
  TRUE AS has_sell_out

FROM gold.rpt_sap_customer_reconciliation;

-- Expected grain: one row per calmonth + customer.
-- For rollups, recompute ratios from SUM(value fields); never AVG row ratios.
