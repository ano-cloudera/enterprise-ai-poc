-- Investigasi: dua set kolom identik (totstck/valstck vs totstck_1/valstck_1)
-- di silver.stock_tempo_oct_dec_2024. Tujuan: cari pola pembeda berdasarkan
-- 0stocktype (A/B/D/F/...) supaya bisa dijadikan hipotesis sebelum konfirmasi
-- resmi ke Tempo (lihat T01/T05/T09 di TEMPO_BUSINESS_QUESTIONS_CATALOG.md).
-- Catatan: "rows" adalah reserved word di Impala - dipakai alias row_count.
--
-- HASIL (dijalankan di Impala, 24 Sep 2026):
-- - Q1: totstck == valstck untuk >90% baris di semua stocktype - bukan bug,
--   qty dan value memang sering sama nilainya (unit price = 1? atau value
--   belum di-scale ke IDR di level silver ini).
-- - Q2: mayoritas baris (~81% utk stocktype A) punya totstck != totstck_1,
--   dengan selisih ekstrem (min -17.75jt, max +10.3jt) dan avg_diff yang
--   tidak konsisten arahnya antar stocktype - bukan "set B = set A + offset".
-- - Q3: persentase beda bervariasi liar antar storage location (15%-95%) -
--   bukan soal satu storage location tertentu.
-- - Q4: PALING PENTING - persentase baris identik FLAT ~31% di ketiga bulan
--   (Okt 30.7%, Nov 30.8%, Des 31.4%). Kalau set B = snapshot bulan lain
--   atau versi ter-update, persentase ini seharusnya bergeser jelas antar
--   bulan. Flat berarti ini BUKAN soal waktu/snapshot - dua sumber/definisi
--   yang independen sejak awal.
-- - Q5: ada baris dengan set A jutaan tapi set B = 0 (dan sebaliknya) -
--   bukan rounding/unit, kemungkinan dua kategori/movement type stock yang
--   berbeda secara struktural.
-- KESIMPULAN: pola terlalu tidak konsisten untuk ditebak dari data saja.
-- Tetap perlu konfirmasi resmi Tempo - gunakan sample dari Q5 sebagai
-- contoh konkret saat bertanya (bukan "ada dua kolom" tapi "kenapa baris
-- material X di plant Y bulan Z punya set A jutaan tapi set B = 0").

-- 1. Apakah totstck selalu sama dengan valstck dalam satu set (qty == value)?
--    Kalau ya di semua baris, salah satu kolom itu redundant/mislabeled.
SELECT
    c_0stocktype,
    COUNT(*) AS row_count,
    SUM(CASE WHEN totstck = valstck THEN 1 ELSE 0 END) AS set_a_qty_eq_val,
    SUM(CASE WHEN totstck_1 = valstck_1 THEN 1 ELSE 0 END) AS set_b_qty_eq_val
FROM silver.stock_tempo_oct_dec_2024
GROUP BY c_0stocktype
ORDER BY row_count DESC;

-- 2. Selisih set A vs set B, dikelompokkan per stocktype - apakah stocktype
--    tertentu (mis. "A" = unrestricted) punya selisih konsisten dari yang lain?
SELECT
    c_0stocktype,
    COUNT(*) AS row_count,
    SUM(CASE WHEN totstck = totstck_1 THEN 1 ELSE 0 END) AS identical_rows,
    SUM(CASE WHEN totstck <> totstck_1 THEN 1 ELSE 0 END) AS differing_rows,
    ROUND(AVG(totstck - totstck_1), 2) AS avg_diff,
    MIN(totstck - totstck_1) AS min_diff,
    MAX(totstck - totstck_1) AS max_diff
FROM silver.stock_tempo_oct_dec_2024
GROUP BY c_0stocktype
ORDER BY row_count DESC;

-- 3. Apakah selisih berkorelasi dengan storage location (0stor_loc) tertentu?
SELECT
    c_0stor_loc,
    COUNT(*) AS row_count,
    SUM(CASE WHEN totstck <> totstck_1 THEN 1 ELSE 0 END) AS differing_rows,
    ROUND(100.0 * SUM(CASE WHEN totstck <> totstck_1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_differing
FROM silver.stock_tempo_oct_dec_2024
GROUP BY c_0stor_loc
ORDER BY row_count DESC
LIMIT 20;

-- 4. Apakah selisih berubah antar bulan (mis. set B = set A bulan sebelumnya,
--    atau set B = snapshot yang di-update belakangan)?
SELECT
    c_0calmonth,
    COUNT(*) AS row_count,
    SUM(CASE WHEN totstck = totstck_1 THEN 1 ELSE 0 END) AS identical_rows,
    ROUND(100.0 * SUM(CASE WHEN totstck = totstck_1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_identical
FROM silver.stock_tempo_oct_dec_2024
GROUP BY c_0calmonth
ORDER BY c_0calmonth;

-- 5. Baris dengan selisih ekstrem (>50% beda) - untuk sample konkret yang
--    bisa dibawa ke Tempo sebagai contoh nyata saat menanyakan definisi.
SELECT
    c_0material, plant, c_0stocktype, c_0stor_loc, c_0calmonth,
    totstck AS set_a_qty, totstck_1 AS set_b_qty,
    ROUND(100.0 * (totstck_1 - totstck) / NULLIF(totstck, 0), 1) AS pct_diff
FROM silver.stock_tempo_oct_dec_2024
WHERE totstck > 0
  AND ABS(totstck_1 - totstck) > 0.5 * totstck
ORDER BY ABS(totstck_1 - totstck) DESC
LIMIT 20;
