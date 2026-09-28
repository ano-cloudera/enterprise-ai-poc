-- Semantic Sales Office Q4 performance view.
-- This dataset is quarter aggregate and does not support monthly trends.

CREATE VIEW gold.rpt_sales_office_performance_semantic AS
SELECT
  reporting_period,
  period_start_calmonth,
  period_end_calmonth,
  reporting_grain,

  sales_off AS sales_office,

  CAST(ROUND(sales_bill_val, 2) AS DECIMAL(38,2))
    AS sell_in_bill_val,

  sales_lines AS sales_billing_lines,

  CAST(ROUND(picking_delay_rate, 6) AS DECIMAL(18,6))
    AS picking_delay_rate,

  CAST(ROUND(avg_pick_min, 2) AS DECIMAL(18,2))
    AS average_picking_minutes,

  pick_rows AS picking_rows,

  CAST(ROUND(avg_unload_min, 2) AS DECIMAL(18,2))
    AS average_unloading_minutes,

  unload_rows AS unloading_rows,

  has_sales AS has_sell_in,
  has_picking,
  has_unloading,

  CAST(ROUND(pick_rows_per_sales_line, 6) AS DECIMAL(18,6))
    AS picking_rows_per_sales_line

FROM gold.rpt_sales_office_performance;

-- Expected grain: one row per reporting_period + sales_office.
