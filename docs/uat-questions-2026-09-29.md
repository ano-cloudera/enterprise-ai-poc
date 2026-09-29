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
| 5 | Sales office Jakarta itu kontribusinya berapa ke total sell-in? | `sales_office_material_sell_in_value` atau `sales_office_sell_in_value` | | |
| 6 | Berapa lama sih stok kita bakal habis kalau lihat dari kecepatan jualnya sekarang? | `months_of_stock_cover` (dengan caveat: proxy, bukan KPI resmi) | | |
| 7 | Ada gap gak antara yang kita tagih (billing) sama yang kita kirim (DO)? | `material_delivery_order_quantity`/`amount` vs billing, atau metric gap terkait | | |
| 8 | **[DI LUAR KONTEKS]** Berapa proyeksi sales kita untuk Q1 2025? | `unsupported` — di luar periode governed (Okt–Des 2024), tidak ada model forecast | | |
| 9 | **[DI LUAR KONTEKS]** Kalau naikin harga 10%, sales bakal turun berapa persen? | `unsupported` — elastisitas harga tidak governed | | |

## 2. B2B/Sell-Out

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Branch mana yang B2B sell-out-nya paling tinggi bulan ini? | `b2b_branch_sell_out_value` per branch | | |
| 2 | Customer B2B mana yang paling banyak belanja ke kita per PLU? | `b2b_customer_material_plu_value` | | |
| 3 | E-store mana yang paling aktif transaksi di bawah cabang Jakarta? | `b2b_branch_sell_out_value`/`quantity` per e_store, filter branch | | |
| 4 | Bandingkan sell-out per KA group deh | `b2b_material_plu_value` per ka_group | | |
| 5 | Berapa banyak sih PLU yang aktif transaksi bulan Desember? | `b2b_material_plu_value`/`quantity`, distinct kode_plu, atau `b2b_sku_coverage`-style count | | |
| 6 | **[DI LUAR KONTEKS]** Berapa margin kita dari jualan B2B ke Indomaret? | `unsupported` — margin/COGS belum di-approve bisnis | | |
| 7 | **[DI LUAR KONTEKS]** Kenapa sell-out kita ke branch Surabaya turun terus 3 bulan ini? | `unsupported` — data observasional 3 bulan, tidak bisa klaim kausalitas/tren sebab-akibat | | |

## 3. Stock Tempo

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Stok gudang kita sekarang berapa banyak sih per material? | `material_warehouse_stock_quantity` atau `stock_tempo_total_qty` | | |
| 2 | Plant mana yang stoknya paling numpuk? | `stock_tempo_total_qty`/`value` per plant | | |
| 3 | Coba kasih nilai stok gudang Tempo per bulan | `stock_tempo_value` per calmonth | | |
| 4 | **[DI LUAR KONTEKS]** Kapan kira-kira kita perlu re-order stok berdasarkan tren sekarang? | `unsupported` — tidak ada model reorder-point/forecast | | |

## 4. Stock SAT-IDM

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Stok di DC partner sekarang berapa ya per PLU? | `sat_idm_dc_stock_quantity` | | |
| 2 | Kalau di level toko/store gimana, stoknya berapa? | `sat_idm_store_stock_quantity` | | |
| 3 | DC mana yang stoknya paling kecil bulan ini? | `sat_idm_dc_stock_quantity` per dcname, order asc | | |
| 4 | Coba jumlahin total stok DC sama stok toko, jadi berapa total pipeline kita? | **Harus ditolak/klarifikasi** — DC Stock dan Store Stock dikonfirmasi Tempo sebagai 2 level analisis terpisah, tidak boleh dijumlahkan | | |
| 5 | **[SENGAJA TES BATASAN]** Kenapa stok di toko selalu lebih gede dari stok DC? Itu wajar gak? | Boleh jelaskan pola data (storestock > dcstock di ~79% baris) tapi **tidak boleh** menyimpulkan sebagai rasio/imbalance KPI resmi | | |

## 5. SAT OOS

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Berapa persen toko yang kosong stoknya pas disurvei bulan lalu? | `sat_oos_rate` | | |
| 2 | Material apa yang paling sering kosong di rak? | `sat_oos_rate` per material_code | | |
| 3 | Customer/toko mana yang paling sering ngalamin stok kosong? | `sat_oos_rate` per cust_id/cust_code | | |
| 4 | **[DI LUAR KONTEKS]** OOS ini pengaruh ke penurunan sales berapa besar sih? | `unsupported` — data 3 bulan observasional tidak cukup untuk klaim kausalitas ke sales | | |

## 6. Service Level

| # | Pertanyaan | Ekspektasi | Hasil | Status |
|---|---|---|---|---|
| 1 | Fill rate kita sekarang berapa secara keseluruhan? | `company_fill_rate` | | |
| 2 | Material apa yang fill rate-nya paling jelek? | `material_fill_rate` per material, order asc | | |
| 3 | Sales office mana yang fill rate-nya paling rendah? | `sales_office_service_fill_rate` per sales_off | | |
| 4 | Ada gap gak antara PO yang masuk sama DO yang kekirim? | `service_unfulfilled_quantity` (PO-DO gap) | | |
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
