-- DRAFT Gold view Fase B (view gabungan lintas domain, journey
-- Stock Tempo -> Sales -> B2B -> SAT-IDM -> OOS).
-- Lihat TEMPO_DATAMART_PLAN.md §8.1. Status: DRAFT, belum dieksekusi/deploy.
-- Prasyarat: Fase A (19_..., 20_...) sudah dibangun & tervalidasi lebih dulu,
-- karena view B ini JOIN ke view Fase A / ke Gold governed lama, bukan ke silver
-- langsung (biar tidak duplikasi logika agregasi).

-- ============================================================
-- View A: gold.corr_stock_tempo_sales_material_month
-- Menyambungkan: Stock Tempo <-> Sales
-- Join key: material + calmonth (dua-duanya sudah governed di grain ini)
-- Cakupan katalog: T07 (stok tinggi, sell-in rendah = indikasi macet)
-- ============================================================
CREATE VIEW gold.corr_stock_tempo_sales_material_month AS
SELECT
    st.calmonth,
    st.material,
    st.total_stock_qty,
    st.stock_value,
    sl.sell_in_bill_val,
    sl.sell_in_bill_qty,
    ROUND(st.total_stock_qty / NULLIF(sl.sell_in_bill_qty, 0), 2) AS stock_to_sell_in_ratio
FROM gold.corr_stock_tempo_month_seta st
LEFT JOIN gold.rpt_sap_material_month_semantic sl
    ON st.material = sl.material
   AND st.calmonth = sl.calmonth;
-- Nama kolom fisik dikonfirmasi dari tempo_core.ossie.yaml (metric
-- material_sell_in_value/quantity -> expression SUM(material_360.sell_in_bill_val)
-- / SUM(material_360.sell_in_bill_qty)); material_360 = alias dataset untuk
-- gold.rpt_sap_material_month_semantic, jadi kolom fisiknya sell_in_bill_val
-- / sell_in_bill_qty, BUKAN nama metric OSSIE itu sendiri.

-- ============================================================
-- View B: gold.corr_sales_b2b_material_month
-- Menyambungkan: Sales (Sell-In) <-> B2B (Sell-Out ke DC)
-- Join key: material + calmonth
-- Cakupan katalog: perkuat B06 (gap Sell-In vs Sell-Out per material)
-- ============================================================
CREATE VIEW gold.corr_sales_b2b_material_month AS
SELECT
    sl.calmonth,
    sl.material,
    sl.sell_in_bill_val,
    b2b.b2b_bill_val   AS material_sell_out_value,
    ROUND(b2b.b2b_bill_val / NULLIF(sl.sell_in_bill_val, 0), 4) AS sell_out_to_sell_in_ratio
FROM gold.rpt_sap_material_month_semantic sl
LEFT JOIN (
    SELECT
        p.calmonth AS calmonth,
        p.material AS material,
        SUM(p.b2b_bill_val) AS b2b_bill_val
    FROM gold.corr_b2b_material_plu p
    GROUP BY p.calmonth, p.material
) b2b
    ON sl.material = b2b.material
   AND sl.calmonth = b2b.calmonth;

-- ============================================================
-- View C: gold.corr_b2b_satidm_branch_month
-- Menyambungkan: B2B (sell-out ke DC) <-> Stock SAT-IDM (stok DC/store)
-- Join key: branch = dcname (CONFIRMED 26 match, lihat TEMPO_KAMUS_DATA_AI.md §4)
-- Cakupan katalog: I06, I11, B11, B12, B13 -- cluster preskriptif paling penting
-- ============================================================
CREATE VIEW gold.corr_b2b_satidm_branch_month AS
SELECT
    b2b.calmonth,
    b2b.branch,
    b2b.b2b_bill_val          AS branch_sell_out_value,
    idm.bln,
    idm.dc_stock_qty,
    idm.dc_stock_val,
    idm.store_stock_qty,
    idm.store_stock_val
FROM (
    SELECT calmonth, branch, SUM(b2b_bill_val) AS b2b_bill_val
    FROM gold.corr_b2b_branch_estore_month
    GROUP BY calmonth, branch
) b2b
LEFT JOIN (
    SELECT thn, bln, dcname,
           SUM(dc_stock_qty) AS dc_stock_qty,
           SUM(dc_stock_val) AS dc_stock_val,
           SUM(store_stock_qty) AS store_stock_qty,
           SUM(store_stock_val) AS store_stock_val
    FROM gold.rpt_sat_idm_dc_month
    GROUP BY thn, bln, dcname
) idm
    ON UPPER(TRIM(REGEXP_REPLACE(b2b.branch, '^DC ', ''))) = UPPER(TRIM(idm.dcname))
   AND idm.thn = CAST(SUBSTR(CAST(b2b.calmonth AS STRING), 1, 4) AS INT)
   AND idm.bln = CASE SUBSTR(CAST(b2b.calmonth AS STRING), 5, 2)
                   WHEN '10' THEN 'OCT'
                   WHEN '11' THEN 'NOV'
                   WHEN '12' THEN 'DEC'
                 END;
-- Format bln dikonfirmasi (24 Sep 2026): 'OCT'/'NOV'/'DEC' (3-huruf Inggris),
-- BUKAN angka -- dicek via SELECT DISTINCT thn, bln FROM
-- silver.stock_sat_idm_monthly_okt_des_24. CASE di atas cuma cover Q4 2024
-- (cakupan data existing); kalau data lain bulan ditambah nanti, perlu
-- diperluas jadi mapping 12 bulan penuh.
--
-- BUG DITEMUKAN & DIPERBAIKI (24 Sep 2026): match rate awal 0% karena
-- b2b.branch punya prefix "DC " (contoh "DC BALARAJA") sedangkan
-- idm.dcname TIDAK ("BALARAJA") -- literal string tidak pernah sama
-- persis walau secara bisnis itu DC yang sama (confirmed 26 match dari
-- investigasi awal). Fix: strip prefix "DC " dari branch + UPPER/TRIM
-- kedua sisi sebelum dibandingkan.

-- ============================================================
-- View D: gold.corr_satidm_oos_material_month
-- Menyambungkan: Stock SAT-IDM (stok DC/store) <-> SAT OOS (rak toko)
-- Join key: material/PLU
-- Cakupan katalog: I05, O10 -- stok DC ada tapi OOS di rak = distribusi macet DC->store
-- ============================================================
CREATE VIEW gold.corr_satidm_oos_material_month AS
SELECT
    idm.calmonth,
    idm.plu,
    idm.dcname,
    idm.store_stock_qty,
    oos.oos_rate_pct,
    oos.survey_count
FROM (
    SELECT
        CAST(thn AS STRING) ||
        CASE bln WHEN 'OCT' THEN '10' WHEN 'NOV' THEN '11' WHEN 'DEC' THEN '12' END
            AS calmonth,
        plu, dcname, SUM(store_stock_qty) AS store_stock_qty
    FROM gold.rpt_sat_idm_dc_month
    GROUP BY thn, bln, plu, dcname
) idm
LEFT JOIN (
    SELECT
        CAST(YEAR(calmonth_date) AS STRING) ||
        LPAD(CAST(MONTH(calmonth_date) AS STRING), 2, '0') AS calmonth,
        plu,
        SUM(survey_count) AS survey_count,
        ROUND(100.0 * SUM(oos_count) / NULLIF(SUM(survey_count), 0), 2) AS oos_rate_pct
    FROM gold.rpt_sat_oos_material_month
    GROUP BY YEAR(calmonth_date), MONTH(calmonth_date), plu
) oos
    ON idm.plu = oos.plu
   AND idm.calmonth = oos.calmonth;
-- Format bln SAT-IDM dikonfirmasi 'OCT'/'NOV'/'DEC' (sama seperti View C).
-- Join sekarang disertakan calmonth juga (bukan PLU saja) supaya tidak
-- salah gabung PLU yang sama across bulan berbeda. calmonth di sini string
-- 'YYYYMM' hasil konkatenasi -- sesuaikan cast/format kalau tipe Impala beda.

-- Cek cepat setelah semua Fase A ter-create, jalankan satu-satu:
-- SELECT COUNT(*) FROM gold.corr_stock_tempo_sales_material_month;
-- SELECT COUNT(*) FROM gold.corr_sales_b2b_material_month;
-- SELECT COUNT(*) FROM gold.corr_b2b_satidm_branch_month;
-- SELECT COUNT(*) FROM gold.corr_satidm_oos_material_month;
-- Untuk View C & D: cek dulu SELECT DISTINCT bln FROM silver.stock_sat_idm_monthly_okt_des_24;
-- sebelum jalankan, supaya join calmonth/bln tidak silently return 0 baris.
