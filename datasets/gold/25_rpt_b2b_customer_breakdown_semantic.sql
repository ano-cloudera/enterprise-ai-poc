-- REFERENCE ONLY - DO NOT RUN THIS FILE AS ONE BLOCK IN WORKBENCH. Running
-- both CREATE VIEW statements together caused a ParseException in this
-- session's Workbench editor (it appears to have executed the highlighted
-- range as a single statement and choked on the comment/second CREATE VIEW
-- after the first statement's closing semicolon). Run each view from its
-- own single-statement file instead:
--   25a_rpt_b2b_customer_branch_estore_semantic.sql
--   25b_rpt_b2b_customer_material_plu_semantic.sql
-- This file is kept only as a combined reference for the reasoning below.
--
-- DEPLOYED AND VERIFIED IN WORKBENCH (28 Sep 2026): 4,881,348 source rows,
-- 36 distinct customers, 24 distinct sales offices, 36 distinct branches,
-- 20,273 distinct e_stores, 144 distinct materials, 144 distinct kode_plu,
-- 0 null/blank customer. 0 duplicate-grain rows in both views.
-- Reconciliation against the existing governed monthly_executive.b2b_bill_val
-- total matched exactly for all three months (202410: 124,631,747,874.52;
-- 202411: 111,896,507,991.67-.68; 202412: 123,373,703,645.99-.98 - the
-- rollup query's raw double total differed only in trailing float noise
-- from the DECIMAL(38,2)-cast governed total, not a real mismatch).
-- ka_group is confirmed constant ("101" for every one of the 4,881,348
-- rows) - not a bug, the source data simply has one KA group value for
-- this period; documented in both gold view files and the semantic layer
-- so it isn't mistaken for a broken column later.
--
-- B2B customer breakdown, extending the existing branch/e_store and
-- material/PLU gold views with the customer dimension. Requested
-- 2026-09-28 as a follow-up to Sales/Sell-In's customer+sales_office
-- expansion: B2B previously had no customer dimension at all in its gold
-- layer, despite silver.b2b_oct_dec_2024 carrying customer, material,
-- sales_off, branch, e_store, and ka_group together on every row.
--
-- Column names confirmed via DESCRIBE silver.b2b_oct_dec_2024 this
-- session: c_0customer, c_0material, c_0sales_off, branch, e_store,
-- ka_group, kode_plu, c_0bill_qty, bill_val (no c_0 prefix on branch/
-- e_store/ka_group/kode_plu - do not assume the c_0 prefix pattern from
-- Sales carries over to every B2B column).
--
-- Two views, not one six-dimension grain, following the same reasoning
-- already used for corr_b2b_branch_estore_month vs corr_b2b_material_plu
-- (see datasets/audit/19_gold_b2b_branch_estore_plu_draft.sql): sales_off/
-- branch and material/kode_plu are treated as independent dimensions by a
-- direct user decision (TEMPO_KAMUS_DATA_AI.md §4 - "Dimensi B2B yang
-- diperlakukan mandiri"), not because they can't coexist in a query, but
-- to avoid an unreviewed six-way cardinality explosion in a single view.
-- Each existing view gets exactly one new dimension: customer.
--
-- Monetary scale: B2B's bill_val is NOT multiplied by *100 here, unlike
-- Sales - this matches the existing gold.corr_b2b_branch_estore_month,
-- gold.corr_b2b_material_plu, and gold.corr_b2b_customer_month views,
-- none of which scale B2B's bill_val. Do not apply the Sales *100 rule to
-- B2B data.

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
