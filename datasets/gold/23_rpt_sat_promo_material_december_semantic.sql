-- Canonical SAT Promo semantic view for the December 2024 field audit.
-- Grain: reporting_month + material_code + mekanisme + program_status.
-- program_status is a raw source code; no active/inactive mapping is implied.

DROP VIEW IF EXISTS gold.rpt_sat_promo_material_december_semantic;

CREATE VIEW gold.rpt_sat_promo_material_december_semantic AS
SELECT
  202412 AS reporting_month,
  TRIM(CAST(material_code AS STRING)) AS material_code,
  COALESCE(
    NULLIF(TRIM(CAST(mekanisme AS STRING)), ''),
    'UNKNOWN'
  ) AS mekanisme,
  COALESCE(
    NULLIF(TRIM(CAST(program_status AS STRING)), ''),
    'UNKNOWN'
  ) AS program_status,
  COUNT(*) AS promo_observation_count
FROM silver.sat_promo_des_24
WHERE tgl_dcp >= CAST('2024-12-01 00:00:00' AS TIMESTAMP)
  AND tgl_dcp < CAST('2025-01-01 00:00:00' AS TIMESTAMP)
  AND material_code IS NOT NULL
  AND TRIM(CAST(material_code AS STRING)) <> ''
GROUP BY
  TRIM(CAST(material_code AS STRING)),
  COALESCE(NULLIF(TRIM(CAST(mekanisme AS STRING)), ''), 'UNKNOWN'),
  COALESCE(NULLIF(TRIM(CAST(program_status AS STRING)), ''), 'UNKNOWN');
