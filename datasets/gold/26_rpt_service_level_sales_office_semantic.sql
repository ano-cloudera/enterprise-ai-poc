-- Service Level sales_office breakdown, extending the existing
-- calmonth+material grain (gold.corr_service_material_month) with
-- sales_off. Requested 2026-09-28 as a follow-up to the Sales/Sell-In and
-- B2B customer/sales_office expansions.
--
-- Column names confirmed via DESCRIBE + SELECT * on
-- silver.service_level_oct_dec_2024 this session: c_0calmonth,
-- c_0material, c_0sales_off, c_0cust_grp3, c_0af_cgr6, do_qty, po_qty (no
-- c_0 prefix on do_qty/po_qty, matching corr_service_material_month's
-- existing usage).
--
-- Two candidate dimensions were investigated and deliberately excluded:
--   - c_0cust_grp3: confirmed constant ("SL") for all 223,922 rows in
--     this Oct-Dec 2024 period via a direct GROUP BY query in Workbench.
--     Not included as a dimension - it would never produce more than one
--     group, which would mislead a "breakdown by customer group" question
--     into looking supported when the answer is always one row.
--   - c_0af_cgr6 ("Characteristic group SAP" per
--     TEMPO_SERVICE_LEVEL_FIELD_CATALOG.md): NOT constant (10 distinct
--     values, Z01-Z11 minus Z05, confirmed varying row counts from 504 to
--     54,741), but its business meaning is explicitly unconfirmed by
--     Tempo ("arti bisnis Tempo pending"). Excluded from this view - do
--     not add it as a governed dimension until Tempo confirms what it
--     means; exposing an unexplained code as a breakdown dimension would
--     be worse than not offering it.
--
-- Only sales_off is added here: a working PoC assumption ("a branch in a
-- given region"), not yet a Tempo-confirmed business definition - same
-- caveat as the Sales/Sell-In and B2B sales_off dimensions.
--
-- do_qty/po_qty are NOT multiplied by *100, matching the existing
-- gold.corr_service_material_month.
--
-- DEPLOYED AND VERIFIED IN WORKBENCH (28 Sep 2026): DESCRIBE confirmed the
-- schema matches this file exactly (calmonth int, material/sales_off
-- string, service_do_qty/service_po_qty/service_fill_rate double,
-- row_count bigint). 0 duplicate-grain rows. Reconciliation against the
-- existing governed monthly_executive.svc_do_qty/svc_po_qty totals
-- matched EXACTLY for all three months (202410: 98,047,594/129,721,601;
-- 202411: 103,665,145/133,014,803; 202412: 102,306,077/128,654,882) - no
-- rounding noise at all here, unlike the Sales/B2B expansions, since
-- these are raw integer-like quantities rather than DECIMAL(38,2) money.

CREATE VIEW gold.corr_service_sales_office_material_month AS
SELECT
    c_0calmonth      AS calmonth,
    c_0material       AS material,
    c_0sales_off      AS sales_off,
    SUM(do_qty)       AS service_do_qty,
    SUM(po_qty)       AS service_po_qty,
    CASE
      WHEN SUM(po_qty) > 0
      THEN SUM(do_qty) / SUM(po_qty)
    END               AS service_fill_rate,
    COUNT(*)          AS row_count
FROM silver.service_level_oct_dec_2024
WHERE c_0calmonth IS NOT NULL
  AND c_0material IS NOT NULL
  AND c_0sales_off IS NOT NULL
  AND TRIM(CAST(c_0sales_off AS STRING)) <> ''
GROUP BY
    c_0calmonth,
    c_0material,
    c_0sales_off;

-- Expected grain: one row per calmonth + material + sales_off.
