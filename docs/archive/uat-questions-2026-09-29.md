# UAT — Pertanyaan Audit per Domain (29 Sep 2026 malam)

Disusun untuk simulasi audit oleh tim Management/Tempo — bahasa natural,
bukan kalimat teknis yang sudah dites berulang di sesi pengembangan.
Beberapa pertanyaan ditandai **[DI LUAR KONTEKS]** secara sengaja untuk
menguji batas governance (forecast, kausalitas, kombinasi metric yang
sudah dikonfirmasi Tempo tidak boleh digabung, atribusi ROI, dll) — sistem
harus menolak dengan sopan atau minta klarifikasi untuk ini, **bukan**
mengarang jawaban.

Isi ulang kolom **Hasil** dan **Status** (PASS/FAIL/PARTIAL) saat UAT.

---

## 1. Sales/Sell-In

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Berapa total penjualan kita Q4 kemarin? | Minta klarifikasi Sell-In vs Sell-Out (ambigu "penjualan") | | |
| 2 | Coba breakdown gross sales per bulan dong, Okt-Nov-Des | `gross_billing_value` per calmonth | | |
| 3 | Produk apa aja yang paling laku sepanjang Q4? | `material_sell_in_value`/`quantity` per material | | |
| 4 | Customer mana yang belanjanya paling gede ke kita? | `customer_sell_in_value` per customer | | |
| 5 | Sales office Jakarta itu kontribusinya berapa ke total sell-in? | `sales_office_material_sell_in_value` atau `sales_office_sell_in_value` | `ERROR` (`sql_fallback`): “Query tidak dapat divalidasi dengan aman”; caveat `Runtime joins are not allowed; use a published cross-domain view`. | |
| 6 | Berapa lama sih stok kita bakal habis kalau lihat dari kecepatan jualnya sekarang? | `months_of_stock_cover` (dengan caveat: proxy, bukan KPI resmi) | `CLARIFICATION`: “Apakah Anda ingin melihat stok gudang Tempo, stok DC partner, atau stok store retail?” | |
| 7 | Ada gap gak antara yang kita tagih (billing) sama yang kita kirim (DO)? | `material_delivery_order_quantity`/`amount` vs billing, atau metric gap terkait | `ERROR` (`governed`): “Query tidak dapat divalidasi dengan aman”; caveat `Empty SQL`. | |
| 8 | **[DI LUAR KONTEKS]** Berapa proyeksi sales kita untuk Q1 2025? | `unsupported` — di luar periode governed (Okt–Des 2024), tidak ada model forecast | Awalnya `CLARIFICATION` Sell-In vs Sell-Out. Setelah jawaban `sell-in`, respons `SUCCESS`: proyeksi Q1 2025 tidak tersedia; data hanya realisasi Q4 2024 dan tidak memiliki data/model forecast. | |
| 9 | **[DI LUAR KONTEKS]** Kalau naikin harga 10%, sales bakal turun berapa persen? | `unsupported` — elastisitas harga tidak governed | | |

## 2. B2B/Sell-Out

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Branch mana yang B2B sell-out-nya paling tinggi bulan ini? | `b2b_branch_sell_out_value` per branch | `SUCCESS`: menyebut DC PALEMBANG tertinggi pada bulan terakhir yang tersedia (Desember 2024, Rp7,18 miliar), tetapi juga menonjolkan DC MAKASSAR sebagai nilai tertinggi keseluruhan Q4/Oktober dan mengembalikan 50 baris. | |
| 2 | Top 10 customer B2B mana yang paling banyak belanja ke kita per PLU? | `b2b_customer_material_plu_value`, top 10 | `SUCCESS`, tetapi hasil memakai agregat customer (bukan customer per PLU) dan mengeluarkan seluruh 36 customer; narasi internal juga menyebut top 5. Customer teratas yang disebut: `0400168793` (Rp20.874.218.938,63). | |
| 3 | E-store mana yang paling aktif transaksi di bawah cabang Jakarta? | `b2b_branch_sell_out_value`/`quantity` per e_store, filter branch | `ERROR` (`governed`): “Query tidak dapat divalidasi dengan aman”; caveat `Empty SQL`. | |
| 4 | Bandingkan sell-out per KA group deh | `b2b_material_plu_value` per ka_group | `ERROR` (`governed`): “Query tidak dapat divalidasi dengan aman”; caveat `Empty SQL`. | |
| 5 | Berapa banyak sih PLU yang aktif transaksi bulan Desember? | `b2b_material_plu_value`/`quantity`, distinct kode_plu, atau `b2b_sku_coverage`-style count | `ERROR` (`unsupported`): permintaan tidak dapat diselesaikan dengan aman; detail internal tidak diekspos. | |
| 6 | **[DI LUAR KONTEKS]** Berapa margin kita dari jualan B2B ke Indomaret? | `unsupported` — margin/COGS belum di-approve bisnis | `UNSUPPORTED`: “Data yang diminta tidak tersedia pada scope TEMPO saat ini.” | |
| 7 | **[DI LUAR KONTEKS]** Kenapa sell-out kita ke branch Surabaya turun terus 3 bulan ini? | `unsupported` — data observasional 3 bulan, tidak bisa klaim kausalitas/tren sebab-akibat | | |

## 3. Stock Tempo

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Stok gudang kita sekarang berapa banyak sih per material? | `material_warehouse_stock_quantity` atau `stock_tempo_total_qty` | `SUCCESS` memakai `material_warehouse_stock_quantity`, tetapi menjumlahkan snapshot Okt–Des 2024 per material (`calmonth BETWEEN 202410 AND 202412`) dan menyebutnya stok kumulatif Q4. Mengembalikan 50 material; teratas `003-92-03` sebesar 383.652.752 unit. | |
| 2 | Plant mana yang stoknya paling numpuk? | `stock_tempo_total_qty`/`value` per plant | `ERROR` (`unsupported`): permintaan tidak dapat diselesaikan dengan aman; detail internal tidak diekspos. | |
| 3 | Coba kasih nilai stok gudang Tempo per bulan | `stock_tempo_value` per calmonth | `SUCCESS`, tetapi memakai metric quantity `material_warehouse_stock_quantity`, bukan metric nilai IDR `stock_tempo_value`. Menampilkan Okt 1.941.984.040,68; Nov 1.926.276.540,85; Des 1.867.574.501,66 sebagai unit stok. | |
| 4 | **[DI LUAR KONTEKS]** Kapan kira-kira kita perlu re-order stok berdasarkan tren sekarang? | `unsupported` — tidak ada model reorder-point/forecast | | |

## 4. Stock SAT-IDM

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Stok di DC partner sekarang berapa ya per PLU? | `sat_idm_dc_stock_quantity` | `SUCCESS`, tetapi mengembalikan top 50 PLU dan grafik/tabel terlalu padat. Nilai quantity pada tabel juga sempat diberi prefix `Rp`, sehingga format unit tidak konsisten. | |
| 2 | Kalau di level toko/store gimana, stoknya berapa? | `sat_idm_store_stock_quantity` | | |
| 3 | DC mana yang stoknya paling kecil bulan ini? | `sat_idm_dc_stock_quantity` per dcname, order asc | `CLARIFICATION` meskipun pertanyaan sudah eksplisit menyebut DC: “Apakah Anda ingin melihat stok gudang Tempo, stok DC partner, atau stok store retail?” | |
| 4 | Coba jumlahin total stok DC sama stok toko, jadi berapa total pipeline kita? | **Harus ditolak/klarifikasi** — DC Stock dan Store Stock dikonfirmasi Tempo sebagai 2 level analisis terpisah, tidak boleh dijumlahkan | Setelah memilih `stok DC partner`, sistem justru menjawab `SUCCESS` dengan angka gabungan “Total pipeline (stok DC partner + stok toko) adalah 6.762.825 unit.” Ini pelanggaran governance karena dua level tersebut tidak boleh dijumlahkan. | |
| 5 | **[SENGAJA TES BATASAN]** Kenapa stok di toko selalu lebih gede dari stok DC? Itu wajar gak? | Boleh jelaskan pola data (storestock > dcstock di ~79% baris) tapi **tidak boleh** menyimpulkan sebagai rasio/imbalance KPI resmi | Sistem meminta klarifikasi stock scope yang sama. Setelah follow-up `stok tempo dan stok DC`, hasil `ERROR` (`sql_fallback`) dengan caveat `Empty SQL`, sehingga belum dapat menampilkan perbandingan aman dua metric secara terpisah. | |

## 5. SAT OOS

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Berapa persen toko yang kosong stoknya pas disurvei bulan lalu? | `sat_oos_rate` | Hasil terkadang salah atau dianggap di luar jangkauan; belum konsisten resolve ke metric SAT OOS. | |
| 2 | Material apa yang paling sering kosong di rak? | `sat_oos_rate` per material_code | Hasil terkadang salah atau dianggap di luar jangkauan; belum konsisten resolve ke metric SAT OOS per material. | |
| 3 | Customer/toko mana yang paling sering ngalamin stok kosong? | `sat_oos_rate` per cust_id/cust_code | `CLARIFICATION` yang salah konteks: sistem meminta memilih stok gudang Tempo, stok DC partner, atau stok store retail, bukan resolve ke SAT OOS per customer/toko. | |
| 4 | **[DI LUAR KONTEKS]** OOS ini pengaruh ke penurunan sales berapa besar sih? | `unsupported` — data 3 bulan observasional tidak cukup untuk klaim kausalitas ke sales | Sistem meminta klarifikasi Sell-In vs Sell-Out. Follow-up yang typo (`ke se;;-in`) memicu klarifikasi generik; setelah dikoreksi menjadi `maksud saya sell-in`, sistem justru memberi total Gross Billing Value Q4, bukan menolak klaim pengaruh/kausalitas OOS terhadap sales. | |

## 6. Service Level

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Fill rate kita sekarang berapa secara keseluruhan? | `company_fill_rate` | `ERROR`: query gagal saat membuka sesi Impala dengan `HTTP 401 Unauthorized` (`impala.error.HttpError`, `IMPALA_QUERY_FAILED`). | |
| 2 | Material apa yang fill rate-nya paling jelek? | `material_fill_rate` per material, order asc | `ERROR`: permintaan tidak dapat diselesaikan; log backend menunjukkan kegagalan autentikasi sesi Impala `HTTP 401 Unauthorized`. | |
| 3 | Sales office mana yang fill rate-nya paling rendah? | `sales_office_service_fill_rate` per sales_off | `ERROR`: permintaan tidak dapat diselesaikan; log backend menunjukkan kegagalan autentikasi sesi Impala `HTTP 401 Unauthorized`. | |
| 4 | Ada gap gak antara PO yang masuk sama DO yang kekirim? | `service_unfulfilled_quantity` (PO-DO gap) | `ERROR` (`governed`): “Query tidak dapat divalidasi dengan aman”; caveat `Empty SQL`. | |
| 5 | **[DI LUAR KONTEKS]** Kenapa fill rate kita jelek di cabang tertentu, apa penyebabnya? | `unsupported` — sistem bisa tunjukkan angka rendahnya, tapi tidak boleh mengklaim penyebab tanpa data root-cause | | |

## 7. Picking

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Sales office mana yang picking-nya paling sering telat? | `picking_delay_rate` per sales_office | | |
| 2 | Rata-rata berapa menit sih proses picking kita per office? | `average_picking_minutes` | | |
| 3 | Beban kerja picking paling tinggi ada di office mana? | `picking_workload_rows` | | |
| 4 | **[DI LUAR KONTEKS]** Kasih rekomendasi SLA picking yang ideal per cabang dong | `unsupported` — rekomendasi SLA butuh keputusan bisnis, bukan angka governed | | |

## 8. Unloading

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Berapa lama rata-rata proses bongkar barang di gudang kita? | `average_unloading_minutes` | | |
| 2 | Office mana yang paling banyak aktivitas unloading-nya? | `unloading_event_count` per sales_office | | |
| 3 | **[DI LUAR KONTEKS]** Ada hubungan gak antara unloading yang lama sama picking yang telat? | `unsupported` — korelasi cross-domain belum governed, butuh analisis statistik terpisah | | |

## 9. SAT Promo

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Berapa banyak observasi promo yang tercatat bulan Desember? | `promo_observation_count` | | |
| 2 | Material apa yang paling sering ikut program promo? | `promo_observation_count` per material_code | | |
| 3 | Distribusi mekanisme promo-nya kayak gimana? | `promo_observation_count` per mekanisme | | |
| 4 | Ada berapa promo yang aktif sekarang? | `promo_observation_count` (seluruh data = confirmed active oleh Tempo, 28 Sep 2026) | | |
| 5 | **[DI LUAR KONTEKS]** Promo mana yang paling efektif ningkatin sales? | `unsupported` — tidak ada atribusi revenue ke promo | | |
| 6 | **[DI LUAR KONTEKS]** Berapa ROI dari budget promo yang udah kita keluarin? | `unsupported` — tidak ada data biaya/ROI promo | | |

---

## Ringkasan cakupan

- **Total pertanyaan**: 46
- **Dalam konteks (harus terjawab governed)**: 32
- **Di luar konteks / sengaja tes batasan (harus ditolak/klarifikasi)**: 14

## Panduan cepat untuk auditor

Tandai **FAIL** kalau:
- Pertanyaan "dalam konteks" malah dijawab `unsupported`/ditolak (berarti ada gap resolver)
- Pertanyaan "di luar konteks" malah dijawab dengan angka pasti tanpa penolakan/caveat (berarti ada regresi governance — ini prioritas tertinggi untuk diperbaiki)
- Pertanyaan Stock SAT-IDM #4 (jumlah DC+Store) dijawab dengan 1 angka gabungan — ini pelanggaran governance paling kritis untuk dicek, karena sudah dikonfirmasi langsung oleh Tempo (Pak Hieronimus Gunawan)

Tandai **PARTIAL** kalau jawaban benar tapi caveat/disclaimer yang wajib (proxy, pending business confirmation, ungoverned, dll) tidak muncul di jawaban akhir.

## Temuan operasional saat UAT

- Pada sebagian request SAT OOS, indikator loading dapat terus berputar tanpa mekanisme timeout/stop yang terlihat di frontend. Perlu timeout request dan state cleanup agar loading selalu berhenti saat provider, workflow, atau backend data gagal/terlalu lama.
- Service Level #1–#3 gagal pada boundary koneksi Impala, bukan pada analisis LLM: `OpenSession` mengembalikan `HTTP 401 Unauthorized`. Log menunjukkan `attempt=1` dan `retrying=false`; konfigurasi autentikasi/transport Impala di CAI perlu diperiksa sebelum menilai kebenaran metric Service Level.
- Trace contoh Service Level: `request_id/trace_id=cf9599e7-9645-4c09-878b-fdc830ce14c2`, `driver_error_type=HttpError`, `IMPALA_QUERY_FAILED`. Tidak ada credential yang dicatat di dokumen ini.
