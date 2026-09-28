-- Exploratory (non-governed v1): SAT OOS aggregated to calendar month.
-- Grain: one row per survey_month + material_code (+ optional customer).
-- PoC assumption: stok_akhir = 0 counts as OOS observation.

CREATE VIEW gold.rpt_sat_oos_month_exploratory AS
SELECT
  CAST(DATE_TRUNC('month', survey_date) AS DATE) AS survey_month,
  material_code,
  cust_id,
  COUNT(*) AS survey_rows,
  SUM(CASE WHEN stok_akhir = 0 THEN 1 ELSE 0 END) AS oos_events,
  AVG(CASE WHEN stok_akhir = 0 THEN 1.0 ELSE 0.0 END) AS oos_rate
FROM gold.stg_sat_oos
WHERE survey_date BETWEEN '2024-10-01' AND '2024-12-31'
GROUP BY 1, 2, 3;

-- ETL note: gold.stg_sat_oos must expose survey_date from TGL_DCP Excel serial conversion.
