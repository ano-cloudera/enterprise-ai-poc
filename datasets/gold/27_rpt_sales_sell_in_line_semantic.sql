-- Sales/Sell-In transaction-line view for dashboard tools (Tableau/Power BI/
-- Cloudera Data Visualization/etc). Requested 29 Sep 2026: one flexible
-- table from the Sales side only, at transaction-line grain so the
-- dashboard tool handles its own group-by/filter across any combination of
-- material, customer, sales_off, and month - rather than pre-aggregating
-- to one fixed grain (which would force a choice between the existing
-- material_360/customer_material_360/sales_office_material_360 views).
--
-- Grain: one row per source silver.sales_oct_dec_2024 billing line. NOT
-- aggregated - this will have millions of rows (same order of magnitude as
-- the 3,632,241-row silver table itself, confirmed earlier this session).
-- Only use this for a dashboard tool that aggregates client-side/query-time;
-- never SELECT * this into application code that expects a small result
-- set.
--
-- Column names confirmed via DESCRIBE silver.sales_oct_dec_2024 this
-- session: c_0calmonth, c_0customer, c_0material (aliased material in some
-- exports), c_0sales_off, c_0sales_grp, t_group, c_0cust_grp3, matlgrp,
-- bill_val, c_0bill_qty, do_qty, do_amt/do_amount (December file uses the
-- alternate do_amount spelling).
--
-- Monetary scale: bill_val and do_amt/do_amount are stored /100 in silver
-- (see datasets/TEMPO_SALES_FIELD_CATALOG.md's ÷100 note) - multiplied by
-- 100 here to IDR, consistent with every other Sales gold view
-- (corr_sales_material_month, corr_sales_customer_month,
-- corr_sales_sales_office). Do not multiply by 100 again downstream.

CREATE VIEW gold.rpt_sales_sell_in_line_semantic AS
SELECT
    c_0calmonth AS calmonth,
    material,
    c_0customer AS customer,
    c_0sales_off AS sales_off,
    c_0sales_grp AS sales_grp,
    c_0cust_grp3 AS cust_grp3,
    matlgrp AS material_group,

    CAST(ROUND(bill_val * 100, 2) AS DECIMAL(38,2))
      AS sell_in_bill_val,

    c_0bill_qty AS sell_in_bill_qty,
    do_qty AS sales_do_qty,

    CAST(ROUND(COALESCE(do_amt, do_amount) * 100, 2) AS DECIMAL(38,2))
      AS sales_do_amt

FROM silver.sales_oct_dec_2024
WHERE c_0calmonth IS NOT NULL
  AND material IS NOT NULL;

-- Expected grain: one row per source billing line (no dedup/aggregation).
-- calmonth + material + customer + sales_off together do NOT uniquely
-- identify a row - the same combination can legitimately repeat across
-- multiple billing lines in a month (confirmed pattern in this data, see
-- datasets/audit/24_sales_customer_office_breakdown_investigation.sql's
-- source_rows counts). Aggregate downstream in the dashboard tool.
