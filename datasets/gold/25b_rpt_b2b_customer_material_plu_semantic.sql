-- B2B customer breakdown, view 2 of 2. See
-- 25_rpt_b2b_customer_breakdown_semantic.sql for full context/reasoning -
-- this file holds ONLY the second CREATE VIEW statement, split out for the
-- same reason as 25a_rpt_b2b_customer_branch_estore_semantic.sql. Run
-- 25a's statement first, then this file's statement by itself.
--
-- Column names confirmed via DESCRIBE silver.b2b_oct_dec_2024: c_0customer,
-- c_0material, kode_plu, ka_group, c_0bill_qty, bill_val (no c_0 prefix on
-- kode_plu/ka_group). B2B's bill_val is NOT multiplied by *100, matching
-- gold.corr_b2b_material_plu.

CREATE VIEW gold.corr_b2b_customer_material_plu_month AS
SELECT
    c_0calmonth          AS calmonth,
    c_0customer           AS customer,
    c_0material           AS material,
    kode_plu,
    ka_group,
    SUM(c_0bill_qty)      AS b2b_bill_qty,
    SUM(bill_val)         AS b2b_bill_val,
    COUNT(*)              AS row_count
FROM silver.b2b_oct_dec_2024
WHERE c_0customer IS NOT NULL AND TRIM(CAST(c_0customer AS STRING)) <> ''
GROUP BY
    c_0calmonth,
    c_0customer,
    c_0material,
    kode_plu,
    ka_group;

-- Expected grain: one row per calmonth + customer + material + kode_plu +
-- ka_group.
