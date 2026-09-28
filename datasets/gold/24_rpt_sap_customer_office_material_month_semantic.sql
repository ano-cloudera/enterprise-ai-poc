-- Sales/Sell-In customer and sales_office breakdown at the material+month
-- grain. Requested 2026-09-28: Sales/Sell-In previously only supported
-- calmonth and material dimensions (gold.rpt_sap_material_month_semantic);
-- the existing customer/sales_office aggregates
-- (gold.corr_sales_customer_month, gold.corr_sales_sales_office) are
-- coarser - customer-only or Q4-total-only, with no material dimension.
--
-- DEPLOYED AND VERIFIED IN WORKBENCH (28 Sep 2026): 3,632,241 source rows,
-- 79,998 distinct customers, 52 distinct sales offices, 0 null/blank
-- customer or sales_off, 0 duplicate-grain rows in either view.
-- Reconciliation against the existing governed gross_billing_value monthly
-- total matched to the cent for all three months (202410: 1,371,960,298,317;
-- 202411: 1,195,251,225,676; 202412: 1,274,654,263,080 - the customer-rollup
-- query's raw float total differed only in trailing decimal noise from the
-- DECIMAL(38,2)-cast governed total, not a real mismatch). DESCRIBE
-- confirmed both views' schemas match this file exactly.
--
-- sales_office is a working assumption ("a branch in a given region"), not
-- yet a Tempo-confirmed business definition - see
-- datasets/TEMPO_SALES_FIELD_CATALOG.md's note that 0SALES_OFF is
-- "asumsi PoC, follow-up Tempo". Do not present it as confirmed to a user;
-- the metric's business_approval_status carries this caveat forward (see
-- projects/tempo_scan_impala/ossie/tempo_core.ossie.yaml).
--
-- Two separate views instead of one three-way (customer + sales_office +
-- material) grain: a source sales row carries both a customer and a
-- sales_office, but analyzing them together would need confirmation that
-- the pairing is stable/complete for every row - not validated here. Keep
-- the two breakdowns independent until that is checked.
--
-- Monetary scale: BILL_VAL in silver.sales_oct_dec_2024 is stored /100
-- (see datasets/TEMPO_SALES_FIELD_CATALOG.md's ÷100 note); multiply by 100
-- here, consistent with gold.corr_sales_customer_month and
-- gold.corr_sales_sales_office. Do not multiply by 100 again downstream -
-- OSSIE metrics built on these views must not re-scale.

CREATE VIEW gold.rpt_sap_customer_material_month_semantic AS
SELECT
  c_0calmonth AS calmonth,
  material,
  c_0customer AS customer,

  CAST(ROUND(SUM(bill_val) * 100, 2) AS DECIMAL(38,2))
    AS sell_in_bill_val,

  SUM(c_0bill_qty) AS sell_in_bill_qty

FROM silver.sales_oct_dec_2024
WHERE c_0calmonth IS NOT NULL
  AND material IS NOT NULL
  AND c_0customer IS NOT NULL
  AND TRIM(CAST(c_0customer AS STRING)) <> ''
GROUP BY c_0calmonth, material, c_0customer;

-- Expected grain: one row per calmonth + material + customer.

CREATE VIEW gold.rpt_sap_sales_office_material_month_semantic AS
SELECT
  c_0calmonth AS calmonth,
  material,
  lpad(trim(CAST(c_0sales_off AS STRING)), 4, '0') AS sales_office,

  CAST(ROUND(SUM(bill_val) * 100, 2) AS DECIMAL(38,2))
    AS sell_in_bill_val,

  SUM(c_0bill_qty) AS sell_in_bill_qty

FROM silver.sales_oct_dec_2024
WHERE c_0calmonth IS NOT NULL
  AND material IS NOT NULL
  AND c_0sales_off IS NOT NULL
  AND TRIM(CAST(c_0sales_off AS STRING)) <> ''
GROUP BY c_0calmonth, material, lpad(trim(CAST(c_0sales_off AS STRING)), 4, '0');

-- Expected grain: one row per calmonth + material + sales_office.
