-- DRAFT Gold view Fase A (journey Stock Tempo -> Sales -> B2B -> SAT-IDM -> OOS)
-- Lihat TEMPO_DATAMART_PLAN.md §8. Status: DRAFT, belum dieksekusi/deploy.
-- Companion: 19_gold_b2b_branch_estore_plu_draft.sql (view B2B sudah didraft di sana)

-- ============================================================
-- View: gold.corr_stock_tempo_month_seta
-- Sumber: silver.stock_tempo_oct_dec_2024
-- Cakupan katalog: T01, T05, T09 (Set A saja - lihat 16_stock_tempo_set_a_vs_b_investigation.sql)
-- Grain: material + plant + calmonth
-- ============================================================
CREATE VIEW gold.corr_stock_tempo_month_seta AS
SELECT
    c_0calmonth        AS calmonth,
    c_0material         AS material,
    plant,
    SUM(totstck)        AS total_stock_qty,   -- Set A
    SUM(valstck)        AS stock_value,        -- Set A
    SUM(cnsstck)         AS consignment_stock_qty, -- Set A
    COUNT(*)             AS row_count
FROM silver.stock_tempo_oct_dec_2024
GROUP BY
    c_0calmonth,
    c_0material,
    plant;

-- ============================================================
-- View: gold.rpt_sat_idm_dc_month
-- Sumber: silver.stock_sat_idm_monthly_okt_des_24
-- Cakupan katalog: I01-I05, I07, I08, I10
-- Grain: dcname + plu + calmonth (thn+bln digabung jadi calmonth-like)
-- ============================================================
CREATE VIEW gold.rpt_sat_idm_dc_month AS
SELECT
    thn,
    bln,
    dcname,
    plu,
    division,
    SUM(dcstock_qty)     AS dc_stock_qty,
    SUM(dcstock_val)     AS dc_stock_val,
    SUM(storestock_qty)  AS store_stock_qty,
    SUM(storestock_val)  AS store_stock_val,
    COUNT(*)              AS row_count
FROM silver.stock_sat_idm_monthly_okt_des_24
GROUP BY
    thn,
    bln,
    dcname,
    plu,
    division;

-- ============================================================
-- View: gold.rpt_sat_oos_material_month
-- Sumber: silver.sat_oos_okt_des_2024
-- Cakupan katalog: O01-O05
-- Grain: cust_id + material_code + calmonth (dari tgl_dcp)
-- Catatan: Stok_akhir = 0 dipakai sbg definisi OOS (PoC default,
-- belum sign-off Tempo - lihat Kamus §6)
-- ============================================================
CREATE VIEW gold.rpt_sat_oos_material_month AS
SELECT
    CAST(CONCAT(CAST(YEAR(tgl_dcp) AS STRING), '-',
                LPAD(CAST(MONTH(tgl_dcp) AS STRING), 2, '0'), '-01') AS DATE) AS calmonth_date,
    cust_id,
    cust_code,
    material_code,
    plu,
    COUNT(*)                             AS survey_count,
    SUM(CASE WHEN stok_akhir = 0 THEN 1 ELSE 0 END) AS oos_count,
    ROUND(100.0 * SUM(CASE WHEN stok_akhir = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS oos_rate_pct
FROM silver.sat_oos_okt_des_2024
GROUP BY
    YEAR(tgl_dcp),
    MONTH(tgl_dcp),
    cust_id,
    cust_code,
    material_code,
    plu;

-- Cek cepat setelah create:
-- SELECT COUNT(*) FROM gold.corr_stock_tempo_month_seta;
-- SELECT COUNT(*) FROM gold.rpt_sat_idm_dc_month;
-- SELECT COUNT(*) FROM gold.rpt_sat_oos_material_month;
-- Perlu cek fungsi TRUNC/date_trunc yang benar di Impala untuk tgl_dcp -> bulan.
