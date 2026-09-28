-- B2B customer breakdown, view 1 of 2. See
-- 25_rpt_b2b_customer_breakdown_semantic.sql for full context/reasoning -
-- this file holds ONLY the first CREATE VIEW statement, split out because
-- some Workbench SQL editors run a highlighted block as one statement and
-- choke on a second CREATE VIEW plus comments after the first one's
-- closing semicolon. Run this file's statement by itself, then run
-- 25b_rpt_b2b_customer_material_plu_semantic.sql's statement by itself.
--
-- Column names confirmed via DESCRIBE silver.b2b_oct_dec_2024: c_0customer,
-- c_0sales_off, branch, e_store, c_0bill_qty, bill_val (no c_0 prefix on
-- branch/e_store). B2B's bill_val is NOT multiplied by *100, matching
-- gold.corr_b2b_branch_estore_month.

CREATE VIEW gold.corr_b2b_customer_branch_estore_month AS
SELECT
    c_0calmonth         AS calmonth,
    c_0customer          AS customer,
    c_0sales_off         AS sales_off,
    branch,
    e_store,
    SUM(c_0bill_qty)     AS b2b_bill_qty,
    SUM(bill_val)        AS b2b_bill_val,
    COUNT(*)             AS row_count
FROM silver.b2b_oct_dec_2024
WHERE c_0customer IS NOT NULL AND TRIM(CAST(c_0customer AS STRING)) <> ''
GROUP BY
    c_0calmonth,
    c_0customer,
    c_0sales_off,
    branch,
    e_store;

-- Expected grain: one row per calmonth + customer + sales_off + branch +
-- e_store.
