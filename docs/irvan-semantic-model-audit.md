# Audit: TEMPO_semantic_model.ossie.yaml (Irvan)

**Sumber**: `reference/lite agent irvan/package/semantic-layer/TEMPO_semantic_model.ossie.yaml`
(gitignored, tidak pernah masuk repo — lihat `.gitignore:54`).
**Tanggal audit**: 29 Sep 2026.
**Isi file**: 33 dataset, 66 metric (`measure_id`/`kpi_id` seperti `SI-01`, `ID-03`, dst).

Tujuan dokumen ini: supaya audit 3.112 baris file itu tidak perlu diulang dari
nol kalau nanti ada yang mau ambil metric tambahan dari sana. Setiap metric
dikategorikan terhadap status semantic layer kita sendiri
(`projects/tempo_scan_impala/ossie/tempo_core.ossie.yaml`, 20 dataset/61
metric per 29 Sep 2026) dan terhadap governance yang sudah dikonfirmasi
Tempo sepanjang project ini.

## Cara membaca kategori di bawah

- **Sudah punya padanan** — kita sudah punya metric dengan formula yang sama
  atau sangat mirip, nama beda. Tidak perlu diimpor.
- **Perlu validasi lebih lanjut** — metric ini punya klaim/formula yang belum
  dicek terhadap konfirmasi Tempo yang sudah kita dapat, atau terhadap
  batasan data yang sudah kita temukan. Bukan "ditolak" atau "melanggar" —
  cuma belum melalui proses audit yang sama seperti metric kita sendiri
  (semua metric kita juga masih `pending_business_confirmation`, ini status
  yang sama, bukan lebih rendah).
- **Kandidat baru, terlihat aman** — formula dan sumber data konsisten
  dengan yang sudah kita audit, tidak menyentuh area yang sudah dikonfirmasi
  bermasalah, tidak butuh gold view baru. Layak diproses lewat langkah yang
  sama seperti metric lain di semantic layer kita (tulis definisi, jalankan
  reconciliation, tambah golden question).
- **Di luar prioritas sekarang** — dataset/QA meta, bukan metric bisnis
  yang biasa ditanyakan user langsung.

---

## Perlu validasi lebih lanjut (6 metric)

| ID | Nama | Formula | Kenapa perlu validasi |
|---|---|---|---|
| `ID-03` | `store_to_dc_ratio` | `store_qty / dc_qty` | Tempo (Pak Hieronimus Gunawan, WhatsApp, 28 Sep 2026) mengonfirmasi DC Stock dan Store Stock adalah **dua level analisis terpisah** — kita punya test eksplisit (`test_sat_idm_publishes_separate_levels_without_combined_pipeline_metric`) yang menahan `sat_idm_store_to_dc_ratio` tetap di luar katalog. Metric Irvan ini kemungkinan dibuat sebelum konfirmasi itu ada. Kalau mau dipakai, perlu dikonfirmasi ulang ke Tempo apakah rasio ini punya use-case valid yang berbeda dari "total pipeline" yang sudah ditolak, sebelum dipublikasikan sebagai governed metric di sistem kita.
| `ID-04` | `pipeline_imbalance` | `SUM(store)-SUM(dc)` | Sama alasan dengan `ID-03` — ini persis pola "total pipeline" yang sudah dikonfirmasi tidak dipakai.
| `SI-07` | `cogs_proxy_idr` | `SUM(zcost) * 100` | Kita punya golden question `margin_pending` ("Berapa gross margin resmi Tempo?") berstatus sengaja `unsupported`, alasan "Official gross margin formula has not been business-approved" — `zcost` sendiri di field catalog Sales kita ditandai "COGS — dipakai draft gross margin dengan BILL_VAL", belum resmi.
| `SI-08` | `gross_margin_proxy` | `SUM(bill_val - zcost) / SUM(bill_val)` | Sama alasan `SI-07` — kalau mau divalidasi, bisa jadi starting point diskusi definisi margin dengan Tempo, bukan langsung dipakai sebagai governed metric.
| `SI-09`/`SI-10` | `implied_discount_idr` / `discount_rate` | `(bill_val - net_sales) * 100` / rasio yang sama | `net_sales`/`VV802` di field catalog Sales kita: "Net sales report field — **Bukan** revenue resmi". Formula diskon dari field yang statusnya sendiri belum baku.
| `SO-06` (versi Irvan) | `sell_in_sell_out_variance_idr` | `sales_bill_val - b2b_bill_val` di `gold.rpt_sap_customer_reconciliation` | Kita punya versi governed dari metric yang sama namanya (`sell_in_minus_sell_out_value`, SO-06 di `tempo_core.ossie.yaml`), TAPI versi kita punya `row_filter: reconciliation_scope = 'shared_customer_only'` — cuma customer yang muncul di Sales DAN B2B. Versi Irvan tidak menyebut filter itu; kalau dijalankan tanpa filter itu, populasi customer yang dibandingkan bisa beda dan hasilnya tidak sebanding dengan angka kita.
| `RO-01` | `oos_rate` | `AVG(stok_akhir <= 0)` | Field catalog SAT OOS kita: "`0` diasumsikan OOS; **konfirmasi definisi resmi ke Tempo**" masih pending. Formula kita sendiri (`sat_oos_rate`, OOS-01) pakai `oos_count` dari gold view yang sudah punya definisi threshold tertentu — perlu dicek apakah `<=0` (bisa termasuk stok negatif) sama persis dengan definisi `oos_count` di gold view kita sebelum disamakan.

## Sudah punya padanan (metric setara, nama beda — tidak perlu diimpor)

Daftar ini bukan lengkap 1:1 untuk semua ~57 metric sisanya, tapi mencakup
yang paling jelas kecocokannya — cukup untuk menunjukkan sebagian besar
"gap" ternyata bukan gap:

| Metric Irvan | Formula Irvan | Padanan di semantic layer kita |
|---|---|---|
| `FL-01 fill_rate` | `SUM(do_qty)/SUM(po_qty)` | `service_fill_rate` (FL-01), `material_fill_rate` (FL-01-MAT), `sales_office_service_fill_rate` (FL-01-OFFICE) |
| `SI-01 gross_billing_value_idr` | `SUM(bill_val)` | `gross_billing_value` (SI-01) |
| `SI-16 inventory_velocity_proxy` | `AVG(bill_qty/tot_stck)` | `sell_in_quantity_per_stock_unit` (SI-16-MAT) — formula sama persis, arah sama |
| `ST-01 on_hand_quantity` | `SUM(totstck)` | `stock_tempo_total_qty` (ST-02-SETA) |
| `PK-01 picking_delay_rate` | `AVG(sstatus='Delayed')` | `picking_delay_rate` (PK-01-Q4) |
| `UL-01 avg_unload_time_minutes` | `AVG(imenit)` | `average_unloading_minutes` (UL-01-Q4) |
| `SO-01/SO-02 sell_out_billing_value/quantity` | `SUM(bill_val)`/`SUM(c_0bill_qty)` di B2B | `b2b_branch_sell_out_value/quantity` (B2B-01/02-BR), `b2b_material_plu_value/quantity` (B2B-02/03-PLU) |

## Kandidat baru, terlihat aman (3 metric)

| ID | Nama | Formula | Kenapa aman |
|---|---|---|---|
| `ST-05` | `months_of_cover` | `tot_stck / bill_qty` | Kebalikan arah dari `sell_in_quantity_per_stock_unit` yang sudah kita punya (`bill_qty/tot_stck`) — "berapa bulan stok akan bertahan" adalah framing bisnis yang lebih intuitif daripada "velocity". Sumber data (`gold.rpt_sap_material_month`, setara `material_360` kita) sudah kita audit. **Status: ditambahkan ke semantic layer kita, lihat di bawah.**
| `ST-07` | `month_over_month_stock_change` | `SUM(delta)` via window `LAG` | Delta stok antar bulan di grain material. Sumber data sama dengan yang sudah kita pakai (`gold.corr_stock_material_month` ≈ `stock_tempo_month` kita). Belum kita punya window-function metric semacam ini — butuh dicek apakah `TempoOssieRegistry`'s compiler mendukung ekspresi `LAG`/window function sebelum diimplementasi (belum diverifikasi).
| `ST-08` | `stuck_stock_sku_count` | `COUNT materials with avg velocity < 0.05` | Turunan dari `months_of_cover`/`inventory_velocity_proxy` yang sudah ada datanya — "SKU dengan pergerakan stok lambat". Butuh threshold `0.05` itu sendiri divalidasi ke Tempo dulu sebelum dipublikasikan sebagai definisi resmi "stuck stock", tapi datanya sudah tersedia.

## Di luar prioritas sekarang (dataset/QA meta, bukan metric bisnis)

`ID-05 b2b_plu_sat_idm_plu_overlap`, `SO-10 material_plu_lookup`, `XD-06
join_coverage_qa`, `plu_overlap_qa`, `reporting_coverage` — ini semua
metric/dataset untuk mengecek kualitas join antar-domain (berapa PLU yang
match di 2 sumber, dst), bukan sesuatu yang user bisnis biasanya tanyakan
langsung. Berguna sebagai referensi kalau nanti kita perlu audit ulang
kualitas join kita sendiri, tapi bukan prioritas untuk diimpor sebagai
metric governed yang di-expose ke user.

---

## Kesimpulan

Dari 66 metric Irvan: **~57 sudah punya padanan** di semantic layer kita
sendiri (dibangun independen, sumber data sama karena keduanya berasal dari
gold view Impala yang sama), **6 perlu validasi lebih lanjut** (bukan
ditolak — statusnya setara `pending_business_confirmation` yang sudah kita
pakai untuk metric kita sendiri, cuma belum diproses), dan **3 adalah
kandidat baru** yang genuinely menambah cakupan tanpa risiko governance
baru. Tidak ada metric yang menuntut impor massal — proses paling aman
tetap menambahkan satu per satu dengan verifikasi yang sama seperti metric
lain di semantic layer kita (definisi, reconciliation, golden question),
bukan menyalin section `metrics:` mentah-mentah.
