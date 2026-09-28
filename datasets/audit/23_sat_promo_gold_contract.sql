-- SAT Promo Gold-contract admission audit.
-- Read-only except for the separate canonical-view DDL in datasets/gold/.
-- Run every result block in Cloudera Workbench before deploying OSSIE.

DESCRIBE gold.corr_sat_promo_materials;
DESCRIBE silver.sat_promo_des_24;

-- Source period, volume, cardinality, and required-field quality.
SELECT
  COUNT(*) AS total_observations,
  COUNT(DISTINCT material_code) AS distinct_materials,
  COUNT(DISTINCT cust_id) AS distinct_customer_ids,
  COUNT(DISTINCT cust_code) AS distinct_customer_codes,
  COUNT(DISTINCT mekanisme) AS distinct_mechanisms,
  MIN(tgl_dcp) AS min_tgl_dcp,
  MAX(tgl_dcp) AS max_tgl_dcp,
  SUM(CASE WHEN tgl_dcp IS NULL THEN 1 ELSE 0 END) AS null_tgl_dcp,
  SUM(CASE WHEN material_code IS NULL OR TRIM(CAST(material_code AS STRING)) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_material,
  SUM(CASE WHEN mekanisme IS NULL OR TRIM(CAST(mekanisme AS STRING)) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_mekanisme,
  SUM(CASE WHEN program_status IS NULL OR TRIM(CAST(program_status AS STRING)) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_program_status
FROM silver.sat_promo_des_24;

-- All rows admitted to the semantic view must be December 2024 observations.
SELECT
  YEAR(tgl_dcp) AS calendar_year,
  MONTH(tgl_dcp) AS calendar_month,
  COUNT(*) AS total_observations
FROM silver.sat_promo_des_24
GROUP BY YEAR(tgl_dcp), MONTH(tgl_dcp)
ORDER BY calendar_year, calendar_month;

-- `program_status` is raw and unmapped: these are source codes, not
-- active/inactive business labels.
SELECT
  COALESCE(NULLIF(TRIM(CAST(program_status AS STRING)), ''), 'UNKNOWN') AS program_status,
  COUNT(*) AS total_observations,
  COUNT(DISTINCT material_code) AS distinct_materials,
  COUNT(DISTINCT cust_id) AS distinct_customer_ids,
  COUNT(DISTINCT cust_code) AS distinct_customer_codes,
  COUNT(DISTINCT mekanisme) AS distinct_mechanisms
FROM silver.sat_promo_des_24
GROUP BY COALESCE(NULLIF(TRIM(CAST(program_status AS STRING)), ''), 'UNKNOWN')
ORDER BY total_observations DESC;

-- Preserve source mechanism text; UNKNOWN is only for blank/null values.
SELECT
  COALESCE(NULLIF(TRIM(CAST(mekanisme AS STRING)), ''), 'UNKNOWN') AS mekanisme,
  COUNT(*) AS total_observations,
  COUNT(DISTINCT material_code) AS distinct_materials
FROM silver.sat_promo_des_24
GROUP BY COALESCE(NULLIF(TRIM(CAST(mekanisme AS STRING)), ''), 'UNKNOWN')
ORDER BY total_observations DESC;

-- Candidate semantic grain. More than one source row per grain is expected;
-- it becomes promo_observation_count rather than being discarded.
SELECT
  CAST(YEAR(tgl_dcp) * 100 + MONTH(tgl_dcp) AS INT) AS reporting_month,
  TRIM(CAST(material_code AS STRING)) AS material_code,
  COALESCE(NULLIF(TRIM(CAST(mekanisme AS STRING)), ''), 'UNKNOWN') AS mekanisme,
  COALESCE(NULLIF(TRIM(CAST(program_status AS STRING)), ''), 'UNKNOWN') AS program_status,
  COUNT(*) AS promo_observation_count
FROM silver.sat_promo_des_24
WHERE tgl_dcp >= CAST('2024-12-01 00:00:00' AS TIMESTAMP)
  AND tgl_dcp < CAST('2025-01-01 00:00:00' AS TIMESTAMP)
  AND material_code IS NOT NULL
  AND TRIM(CAST(material_code AS STRING)) <> ''
GROUP BY
  CAST(YEAR(tgl_dcp) * 100 + MONTH(tgl_dcp) AS INT),
  TRIM(CAST(material_code AS STRING)),
  COALESCE(NULLIF(TRIM(CAST(mekanisme AS STRING)), ''), 'UNKNOWN'),
  COALESCE(NULLIF(TRIM(CAST(program_status AS STRING)), ''), 'UNKNOWN')
ORDER BY promo_observation_count DESC
LIMIT 100;

-- Existing Irvan view is only a distinct promotional-material list. Confirm
-- its row count matches its material cardinality; it is not the observation
-- fact used for mechanism/status breakdowns.
SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT material) AS distinct_materials,
  SUM(CASE WHEN material IS NULL OR TRIM(CAST(material AS STRING)) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_material
FROM gold.corr_sat_promo_materials;

-- Post-create contract checks for the canonical semantic view.
DESCRIBE gold.rpt_sat_promo_material_december_semantic;

SELECT
  COUNT(*) AS semantic_rows,
  SUM(promo_observation_count) AS source_observations_represented,
  SUM(CASE WHEN promo_observation_count < 0 THEN 1 ELSE 0 END)
    AS negative_observation_rows,
  SUM(CASE WHEN reporting_month <> 202412 THEN 1 ELSE 0 END)
    AS outside_december_rows,
  SUM(CASE WHEN material_code IS NULL OR TRIM(material_code) = '' THEN 1 ELSE 0 END)
    AS null_or_blank_material_rows
FROM gold.rpt_sat_promo_material_december_semantic;

SELECT COUNT(*) AS duplicate_grain_rows
FROM (
  SELECT
    reporting_month,
    material_code,
    mekanisme,
    program_status,
    COUNT(*) AS grain_rows
  FROM gold.rpt_sat_promo_material_december_semantic
  GROUP BY reporting_month, material_code, mekanisme, program_status
  HAVING COUNT(*) > 1
) duplicate_grains;

SELECT
  program_status,
  SUM(promo_observation_count) AS total_observations,
  COUNT(DISTINCT material_code) AS distinct_materials,
  COUNT(DISTINCT mekanisme) AS distinct_mechanisms
FROM gold.rpt_sat_promo_material_december_semantic
GROUP BY program_status
ORDER BY total_observations DESC;
