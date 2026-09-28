-- Investigate: is storestock consistently > dcstock across the whole
-- dataset, or was that just a coincidence in the ~12 rows screenshotted?
-- If consistent, this supports the hypothesis that dcstock = a
-- point-in-time DC snapshot (smaller, more turnover) while storestock =
-- an aggregate across MANY stores under that DC (naturally larger sum),
-- rather than dcstock/storestock being two mutually exclusive slices of
-- one total pipeline.

-- 1. Overall: what % of rows have storestock_qty > dcstock_qty?
SELECT
  COUNT(*) AS total_rows,
  SUM(CASE WHEN storestock_qty > dcstock_qty THEN 1 ELSE 0 END) AS store_gt_dc,
  SUM(CASE WHEN storestock_qty < dcstock_qty THEN 1 ELSE 0 END) AS store_lt_dc,
  SUM(CASE WHEN storestock_qty = dcstock_qty THEN 1 ELSE 0 END) AS store_eq_dc,
  ROUND(100.0 * SUM(CASE WHEN storestock_qty > dcstock_qty THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_store_gt_dc
FROM silver.stock_sat_idm_monthly_okt_des_24;

-- 2. Ratio distribution: storestock_qty / NULLIF(dcstock_qty, 0)
--    A tight, consistent ratio (e.g. always ~2-4x) would support "store
--    is an aggregate of several outlets per DC" as the explanation.
--    A wildly varying ratio (0.1x to 50x) would suggest something else
--    (e.g. different units, or genuinely independent stock pools).
SELECT
  MIN(storestock_qty / NULLIF(dcstock_qty, 0)) AS min_ratio,
  ROUND(AVG(storestock_qty / NULLIF(dcstock_qty, 0)), 2) AS avg_ratio,
  MAX(storestock_qty / NULLIF(dcstock_qty, 0)) AS max_ratio,
  ROUND(STDDEV(storestock_qty / NULLIF(dcstock_qty, 0)), 2) AS stddev_ratio
FROM silver.stock_sat_idm_monthly_okt_des_24
WHERE dcstock_qty > 0;

-- 3. Sanity check: does the val/qty unit price look consistent between
--    dcstock and storestock (same product, same price expected)? A big
--    mismatch would suggest storestock_val isn't simply "more units of
--    the same stock class" but something priced differently.
SELECT
  plu,
  dcname,
  dcstock_qty,
  dcstock_val,
  ROUND(dcstock_val / NULLIF(dcstock_qty, 0), 0) AS dc_unit_price,
  storestock_qty,
  storestock_val,
  ROUND(storestock_val / NULLIF(storestock_qty, 0), 0) AS store_unit_price
FROM silver.stock_sat_idm_monthly_okt_des_24
WHERE dcstock_qty > 0 AND storestock_qty > 0
LIMIT 20;

-- HASIL (dijalankan di Impala, 28 Sep 2026):
--
-- Query 1: total_rows=11458, store_gt_dc=9053 (79.0%), store_lt_dc=2381
-- (20.8%), store_eq_dc=24 (0.2%). storestock > dcstock is the dominant
-- pattern across the WHOLE dataset, not a coincidence of the ~12
-- screenshotted rows.
--
-- Query 2: min_ratio=-4 (dcstock_qty can be negative in raw data - not
-- investigated further here), avg_ratio=60.69, max_ratio=6838,
-- stddev_ratio=253.56. The ratio is WILDLY inconsistent (not tight
-- around, say, 2-4x) - this rules out the simple hypothesis that
-- storestock is just "several outlets aggregated under one DC" with a
-- roughly stable outlet count per DC. If it were, the ratio would
-- cluster in a narrow band.
--
-- Query 3: dc_unit_price (dcstock_val/dcstock_qty) and store_unit_price
-- (storestock_val/storestock_qty) are nearly IDENTICAL for the same PLU
-- across every DC sampled (both ~5420-5490 for PLU 100264) - confirms
-- dcstock and storestock are priced consistently as the same physical
-- stock class (not two differently-valued categories).
--
-- CONCLUSION: dcstock and storestock behave as two INDEPENDENT stock
-- pools, not a proportional split of one total. No evidence of
-- double-counting (unit price consistency + the fact they're measured
-- at genuinely different physical locations - DC warehouse vs.
-- store-level - both point away from overlap), but also no evidence they
-- can be summed/compared with a fixed ratio assumption. Documented as a
-- PoC-temporary interpretation in TEMPO_KAMUS_DATA_AI.md and
-- TEMPO_STOCK_SAT_IDM_FIELD_CATALOG.md; still needs a real definition
-- from Tempo (open question #5/#6 in the field catalog).
