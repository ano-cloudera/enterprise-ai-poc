-- DRAFT Gold view #1 & #2 (lihat TEMPO_DATAMART_PLAN.md §8).
-- Sumber: silver.b2b_oct_dec_2024 (tidak butuh join lain).
-- Status: DRAFT — belum dieksekusi/deploy, untuk direview dulu.

-- ============================================================
-- View #1: gold.corr_b2b_branch_estore_month
-- Cakupan katalog: B02, B05
-- Grain: branch + e_store + sales_off + calmonth (semua independen,
-- lihat keputusan PoC 24 Sep 2026 - TEMPO_KAMUS_DATA_AI.md §4)
-- ============================================================
CREATE VIEW gold.corr_b2b_branch_estore_month AS
SELECT
    c_0calmonth        AS calmonth,
    c_0sales_off        AS sales_off,
    branch,
    e_store,
    SUM(c_0bill_qty)    AS b2b_bill_qty,
    SUM(bill_val)       AS b2b_bill_val,
    COUNT(*)            AS row_count
FROM silver.b2b_oct_dec_2024
GROUP BY
    c_0calmonth,
    c_0sales_off,
    branch,
    e_store;

-- ============================================================
-- View #2: gold.corr_b2b_material_plu
-- Cakupan katalog: B07, PQ2
-- Grain: material + kode_plu + calmonth (dimensi independen,
-- tidak ada mapping PLU<->material yang dikonfirmasi - lihat B10 unsupported)
-- ============================================================
CREATE VIEW gold.corr_b2b_material_plu AS
SELECT
    c_0calmonth         AS calmonth,
    c_0material          AS material,
    kode_plu,
    ka_group,
    SUM(c_0bill_qty)     AS b2b_bill_qty,
    SUM(bill_val)        AS b2b_bill_val,
    COUNT(*)             AS row_count
FROM silver.b2b_oct_dec_2024
GROUP BY
    c_0calmonth,
    c_0material,
    kode_plu,
    ka_group;

-- Cek cepat setelah create: row count wajar & tidak ada grain meledak
-- (bandingkan row_count di sini vs jumlah baris silver.b2b_oct_dec_2024 asli)
-- SELECT COUNT(*) FROM gold.corr_b2b_branch_estore_month;
-- SELECT COUNT(*) FROM gold.corr_b2b_material_plu;
