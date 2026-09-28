-- Investigasi nilai `program_status` di gold.stg_sat_promo - lihat P02/P10
-- di TEMPO_BUSINESS_QUESTIONS_CATALOG.md.
--
-- HASIL (dicek user di Impala, 24 Sep 2026): nilai yang muncul adalah
-- X, Y, T - tanpa makna resmi dari Tempo. Keputusan: kolom ini dikeluarkan
-- dari scope PoC sekarang (P02/P10 -> unsupported), bukan ditebak.

SELECT program_status, COUNT(*) AS row_count
FROM gold.stg_sat_promo
GROUP BY program_status
ORDER BY row_count DESC;
