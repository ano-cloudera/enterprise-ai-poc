-- Exploratory (non-governed v1): SAT Promo December 2024 + flags for Sales join.
-- Grain: observation row; use aggregates for PQ1/P01 catalog questions.

CREATE VIEW gold.rpt_sat_promo_december_exploratory AS
SELECT
  promo_date,
  cust_id,
  cust_code,
  material_code,
  mekanisme,
  program_status
FROM gold.stg_sat_promo
WHERE promo_date >= '2024-12-01' AND promo_date < '2025-01-01';

CREATE VIEW gold.rpt_promo_material_coverage_des AS
SELECT
  material_code,
  COUNT(*) AS promo_observations,
  COUNT(DISTINCT cust_id) AS promo_stores,
  COUNT(DISTINCT mekanisme) AS mekanisme_types
FROM gold.rpt_sat_promo_december_exploratory
GROUP BY material_code;

-- Join to Sales Des (exploratory, not OSSIE v1):
-- gold.stg_fact_sales WHERE calmonth = 202412 ON material_id = material_code
