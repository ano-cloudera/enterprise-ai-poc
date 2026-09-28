# TEMPO Semantic Field Catalog

**Purpose:** Mencatat nama field fisik, nama bisnis, formula, grain, caveat, dan perubahan semantic sebelum dimasukkan ke Apache Ossie.

**Scope saat ini:**

- `gold.rpt_service_level_material_month`
- `gold.rpt_sap_customer_reconciliation`

**Prinsip governance:**

1. Nilai monetary pada Gold sudah dalam IDR. Jangan dikalikan `100` lagi.
2. Ratio agregat dihitung dari `SUM(numerator) / SUM(denominator)`, bukan `AVG(row_ratio)`.
3. Rekonsiliasi Sell-In vs Sell-Out hanya mencakup customer yang ada di kedua domain.
4. Field berstatus `legacy` dipertahankan untuk kompatibilitas, tetapi tidak dipublikasikan sebagai KPI utama.

**Provenance fields pada `gold.rpt_semantic_metric_catalog`:**

| Field | Meaning |
|---|---|
| `definition_origin` | Sumber definisi: adaptasi katalog Irvan atau hasil turunan audit |
| `original_kpi_id` | KPI induk pada `TEMPO_KPI_catalog.md` |
| `adaptation_type` | Bentuk perubahan: rename, scoped variant, inverse, data-quality, atau derived |
| `business_approval_status` | Status persetujuan bisnis terpisah dari technical governance status |

Tidak ada KPI pada Semantic Contract v1 yang dianggap resmi hanya karena lolos technical audit. Semua KPI bisnis tetap berstatus `pending_business_confirmation` sampai dikonfirmasi Tempo.

---

## 1. Service Level

**Semantic source view:** `gold.rpt_service_level_material_month_semantic`
**Upstream business view:** `gold.rpt_service_level_material_month`
**Grain:** `calmonth + material`

| KPI ID | Physical field | Business name | Formula / rule | Unit | Business description | Status |
|---|---|---|---|---|---|---|
| FL-01 | `fill_rate` | Fill Rate | `SUM(do_qty) / NULLIF(SUM(po_qty), 0)` | ratio / percent | Persentase jumlah pesanan yang berhasil dipenuhi. Pada level aggregate wajib dihitung ulang dari total DO dan PO. | approved candidate |
| FL-06 | `fill_rate_band` | Fill Rate Band | `unknown` jika NULL; `low_fill` jika `< 0.5`; `medium_fill` jika `0.5–<0.8`; `high_fill` jika `>=0.8` | category | Klasifikasi tingkat pemenuhan order untuk membantu prioritas investigasi material. | fixed, pending business approval |
| FL-04 | `po_qty` | Purchase Order Quantity | `SUM(po_qty)` | quantity | Jumlah unit yang dipesan customer dan menjadi denominator Fill Rate. | approved candidate |
| FL-05 | `do_qty` | Fulfilled Delivery Quantity | `SUM(do_qty)` | quantity | Jumlah unit yang berhasil dikirim/dipenuhi. | approved candidate |
| SI-CONTEXT-01 | `sales_bill_qty` | Sell-In Billing Quantity Context | Dari `gold.corr_sales_material_month.bill_qty` | quantity | Volume Sell-In untuk memberi konteks penjualan pada analisis Service Level. Bukan komponen formula Fill Rate. | contextual |
| SI-CONTEXT-02 | `sales_bill_val` | Sell-In Billing Value Context | Dari `gold.corr_sales_material_month.bill_val` | IDR | Nilai Sell-In yang sudah dinormalisasi ke IDR pada Gold. | contextual |
| ST-CONTEXT-01 | `tot_stck` | Warehouse Stock Context | Dari `gold.corr_stock_material_month.tot_stck` | quantity | Stok gudang Tempo pada material dan bulan yang sama. Bukan stok customer/outlet. | contextual |

### Perubahan 2026-09-24

| Field | Sebelum | Sesudah | Alasan |
|---|---|---|---|
| `fill_rate_band` | NULL `fill_rate` masuk ke `high_fill` melalui default `ELSE` | NULL `fill_rate` masuk ke `unknown` | Mencegah data fulfillment yang tidak tersedia terlihat sehat |

### Validasi

- `low_fill`: 604 material-month, range `0–<0.5`
- `medium_fill`: 824 material-month, range `0.5–<0.8`
- `high_fill`: 794 material-month, range `0.8–1`
- `unknown`: 1 material-month, `fill_rate IS NULL`
- Total: 2,223 material-month
- Has Sell-In: 2,182 material-month
- Has Stock: 2,192 material-month
- Full Service Level + Sell-In + Stock context: 2,182 material-month (98.16%)

---

## 2. Sell-In vs Sell-Out Customer Reconciliation

**Semantic source view:** `gold.rpt_sap_customer_reconciliation_semantic`
**Upstream business view:** `gold.rpt_sap_customer_reconciliation`
**Grain:** `calmonth + customer`
**Scope:** Hanya customer yang muncul di Sales dan B2B karena menggunakan `INNER JOIN`.

| KPI ID | Physical field | Business name | Formula / rule | Unit | Business description | Status |
|---|---|---|---|---|---|---|
| SO-06 | `bill_val_variance` | Sell-In Minus Sell-Out Value | `sales_bill_val - b2b_bill_val` | IDR | Selisih nilai Sell-In dan Sell-Out. Positif berarti Sell-In lebih besar; negatif berarti Sell-Out lebih besar. | approved candidate |
| SO-07 | `sell_out_to_sell_in_ratio` | Sell-Out to Sell-In Value Ratio | `b2b_bill_val / NULLIF(sales_bill_val, 0)` | ratio / percent | Mengukur keseimbangan nilai Sell-Out terhadap Sell-In. Indikator arah pergerakan channel, bukan official sell-through karena opening stock belum diperhitungkan. | approved candidate with caveat |
| SO-07-INVERSE | `sell_in_to_sell_out_ratio` | Sell-In to Sell-Out Value Ratio | `sales_bill_val / NULLIF(b2b_bill_val, 0)` | ratio | Perspektif kebalikan untuk melihat berapa kali nilai Sell-In dibanding Sell-Out. | supporting |
| LEGACY-SO-RATIO | `sales_to_b2b_ratio` | Legacy Sales to B2B Ratio | Sama dengan `sell_in_to_sell_out_ratio` | ratio | Field lama yang dipertahankan agar query existing tidak rusak. Jangan expose sebagai KPI utama. | legacy / deprecated |
| SO-06-PCT | `bill_val_pct_variance` | Sell-In vs Sell-Out Absolute Variance Rate | `ABS(sales_bill_val - b2b_bill_val) / NULLIF(b2b_bill_val, 0)` | ratio / percent | Besarnya gap absolut relatif terhadap nilai Sell-Out. Tidak menunjukkan arah; gunakan `bill_val_variance` untuk arah. | supporting |
| SI-01-SHARED | `sales_bill_val` | Shared-Customer Sell-In Value | Dari `gold.corr_sales_customer_month.bill_val` | IDR | Nilai Sell-In hanya untuk customer yang juga ditemukan pada B2B. Bukan total seluruh customer Sales. | scoped metric |
| SO-01-SHARED | `b2b_bill_val` | Shared-Customer Sell-Out Value | Dari `gold.corr_b2b_customer_month.bill_val` | IDR | Nilai Sell-Out untuk shared-customer scope. | scoped metric |

### Perubahan 2026-09-24

| Sebelum | Sesudah | Alasan |
|---|---|---|
| Hanya `sales_to_b2b_ratio` dengan arah formula yang kurang eksplisit | Tambah `sell_in_to_sell_out_ratio` dan `sell_out_to_sell_in_ratio`; field lama tetap tersedia | Menghindari salah interpretasi arah numerator dan denominator |

Semantic wrapper tidak mengekspos `sales_to_b2b_ratio`; field legacy hanya tetap tersedia pada upstream view untuk backward compatibility.

### Coverage validation

- Customer-month rows: 108
- Shared customers: 36
- Reporting months: 3
- Period: 202410–202412
- `reconciliation_scope`: `shared_customer_only`
- Sell-Out/Sell-In value ratio:
  - 202410: 0.474880
  - 202411: 0.635635
  - 202412: 0.666062

### Aturan agregasi

Benar:

```sql
SUM(b2b_bill_val) / NULLIF(SUM(sales_bill_val), 0)
```

Salah:

```sql
AVG(sell_out_to_sell_in_ratio)
```

### Interpretasi bisnis

- `sell_out_to_sell_in_ratio ≈ 1`: Sell-In dan Sell-Out relatif seimbang.
- `< 1`: Sell-In lebih besar daripada Sell-Out; perlu cek Stock SAT-IDM sebelum menyimpulkan penumpukan.
- `> 1`: Sell-Out melebihi Sell-In periode berjalan; dapat menunjukkan penarikan stok periode sebelumnya.
- Perbandingan nilai dapat dipengaruhi perbedaan harga Sell-In dan harga retail. Untuk replenishment, quantity ratio lebih representatif.

---

## 3. Monthly Executive Performance

**Semantic source view:** `gold.rpt_sap_monthly_executive_semantic`
**Upstream business view:** `gold.rpt_sap_monthly_executive`
**Grain:** `calmonth`
**Scope:** 202410–202412

| KPI ID | Physical field | Business name | Formula / rule | Unit | Business description | Status |
|---|---|---|---|---|---|---|
| SI-01 | `sales_bill_val` | Monthly Sell-In Billing Value | `SUM(gold.corr_sales_material_month.bill_val)` | IDR | Total nilai Sell-In bulanan yang sudah dinormalisasi ke IDR pada Gold. | approved candidate |
| SI-02 | `sales_bill_qty` | Monthly Sell-In Billing Quantity | `SUM(bill_qty)` | quantity | Total unit yang ditagihkan pada bulan berjalan. | approved candidate |
| SI-03 | `sales_do_qty` | Monthly Sales DO Quantity | `SUM(do_qty)` | quantity | Total delivery-order quantity dari Sales extract. | approved candidate |
| SI-04 | `sales_do_amt` | Monthly Sales DO Amount | `SUM(do_amt)` | IDR | Total nilai delivery order yang sudah dinormalisasi di Gold. | approved candidate |
| FL-01-EXEC | `svc_fill_rate` | Company Monthly Fill Rate | `SUM(svc_do_qty) / NULLIF(SUM(svc_po_qty), 0)` | ratio / percent | Persentase pemenuhan order perusahaan per bulan. | approved candidate |
| ST-CONTEXT-EXEC | `stock_qty` | Monthly Warehouse Stock Snapshot | `SUM(tot_stck)` | quantity | Total snapshot stok gudang pada bulan berjalan. Bukan stock flow. | contextual |
| SO-01-EXEC | `b2b_bill_val` | Monthly Sell-Out Billing Value | `SUM(b2b_bill_val)` | IDR | Total nilai Sell-Out bulanan pada channel B2B. | approved candidate |
| SI-DQ-01 | `do_amt_to_bill_val_ratio` | DO Amount to Billing Value Ratio | `sales_do_amt / NULLIF(sales_bill_val, 0)` | ratio | Indikator alignment nilai DO terhadap billing; dapat digunakan untuk mendeteksi anomali. | data quality metric |
| ST-SI-01 | `stock_to_sales_bill_qty_ratio` | Stock to Sell-In Quantity Ratio | `stock_qty / NULLIF(sales_bill_qty, 0)` | ratio | Proxy coverage stok terhadap volume billing bulanan. Tidak memperhitungkan opening/closing flow. | supporting |

### Perubahan 2026-09-24

Driving month universe sekarang berasal dari union:

- Sales
- Stock
- Service Level
- B2B

Sebelumnya Service Level tidak dimasukkan sebagai sumber reporting month.

Monetary dan ratio output juga distandardisasi pada semantic wrapper:

- Monetary: `DECIMAL(38,2)`
- Ratio: `DECIMAL(18,6)`
- Quantity: mengikuti numeric source
- Upstream `rpt_sap_monthly_executive` tetap tersedia untuk backward compatibility.

### Validasi

- Bulan tersedia: 202410, 202411, 202412.
- Semua bulan memiliki Sales, Stock, Service Level, dan B2B.
- Fill Rate:
  - 202410: 75.5831%
  - 202411: 77.9350%
  - 202412: 79.5198%
- Recomputed Fill Rate difference: 0 untuk seluruh bulan.

---

## 4. Material 360

**Semantic source view:** `gold.rpt_sap_material_month_semantic`
**Upstream business view:** `gold.rpt_sap_material_month`
**Grain:** `calmonth + material`

| KPI ID | Physical field | Business name | Formula / rule | Unit | Business description | Status |
|---|---|---|---|---|---|---|
| SI-01-MAT | `sell_in_bill_val` | Material Sell-In Billing Value | Gold Sales `bill_val` | IDR | Nilai Sell-In per material dan bulan. | approved candidate |
| SI-02-MAT | `sell_in_bill_qty` | Material Sell-In Billing Quantity | Gold Sales `bill_qty` | quantity | Volume billing Sell-In per material dan bulan. | approved candidate |
| ST-01-MAT | `warehouse_stock_qty` | Material Warehouse Stock Quantity | Gold Stock `tot_stck` | quantity | Snapshot total stok gudang Tempo per material dan bulan. | approved candidate |
| ST-02-MAT | `warehouse_stock_val` | Material Warehouse Stock Value | Gold Stock `val_stck` | IDR | Nilai snapshot stok gudang per material dan bulan. | approved candidate |
| FL-01-MAT | `service_fill_rate` | Material Fill Rate | `service_do_qty / NULLIF(service_po_qty, 0)` | ratio / percent | Tingkat pemenuhan order per material dan bulan. | approved candidate |
| SO-01-MAT | `sell_out_bill_val` | Material Sell-Out Billing Value | Gold B2B `bill_val` | IDR | Nilai Sell-Out B2B per material dan bulan. Hanya tersedia untuk material B2B. | scoped metric |
| SI-16-MAT | `sell_in_qty_per_stock_unit` | Sell-In Quantity per Stock Unit | `sell_in_bill_qty / NULLIF(warehouse_stock_qty, 0)` | ratio | Proxy velocity Sell-In terhadap snapshot stok. Bukan inventory turnover resmi. | supporting |
| SO-07-MAT | `sell_out_to_sell_in_value_ratio` | Material Sell-Out to Sell-In Value Ratio | `sell_out_bill_val / NULLIF(sell_in_bill_val, 0)` | ratio | Perbandingan nilai Sell-Out terhadap Sell-In per material dan bulan. | approved candidate with caveat |
| SO-07-MAT-INVERSE | `sell_in_to_sell_out_value_ratio` | Material Sell-In to Sell-Out Value Ratio | `sell_in_bill_val / NULLIF(sell_out_bill_val, 0)` | ratio | Perspektif kebalikan dari SO-07-MAT. | supporting |
| SI-DQ-02 | `sales_do_amt_to_bill_val_ratio` | Material DO Amount to Billing Value Ratio | `sales_do_amt / NULLIF(sell_in_bill_val, 0)` | ratio | Data-quality/alignment signal antara nilai DO dan billing. | data quality metric |

### Coverage validation

- Total material-month universe: 50,730
- Has Stock: 50,627
- Has Sell-In: 6,564
- Has Service Level: 2,223
- Has Sell-Out: 420
- Has Sell-In + Stock + Service Level: 2,182

### Scope rules

- Sales analysis: filter `has_sell_in = TRUE`.
- Sales vs Stock: filter `has_sell_in AND has_stock`.
- Core Material 360: filter `has_sell_in AND has_stock AND has_service_level`.
- Sell-In vs Sell-Out: filter `has_sell_in AND has_sell_out`.
- Universe didominasi Stock; jangan menghitung average cross-domain tanpa coverage filter.
- Value ratio dapat dipengaruhi perbedaan price basis Sell-In dan Sell-Out.
- Reciprocal ratio yang dibulatkan 6 desimal dapat memiliki selisih kecil pada nilai ekstrem; SO-07-MAT adalah arah canonical.

---

## 5. Sales Office Performance (Q4 2024)

**Semantic source view:** `gold.rpt_sales_office_performance_semantic`
**Upstream business view:** `gold.rpt_sales_office_performance`
**Grain:** `sales_office + reporting_period`
**Current reporting period:** `2024Q4` (`202410–202412`)

| KPI ID | Physical field | Business name | Formula / rule | Unit | Business description | Status |
|---|---|---|---|---|---|---|
| SI-13-Q4 | `sell_in_bill_val` | Sales Office Sell-In Value (Q4) | Dari `gold.corr_sales_sales_office.bill_val` | IDR | Total nilai Sell-In per sales office untuk seluruh Q4 2024. | approved candidate |
| SI-LINES-Q4 | `sales_billing_lines` | Sales Billing Lines (Q4) | `COUNT(*)` billing lines | count | Jumlah baris billing Sales per office selama Q4. Bukan jumlah transaksi unik. | contextual |
| PK-01-Q4 | `picking_delay_rate` | Picking Delay Rate (Q4) | `AVG(CASE WHEN sstatus='Delayed' THEN 1 ELSE 0 END)` | ratio / percent | Proporsi baris picking yang berstatus Delayed per sales office selama Q4. | approved candidate |
| PK-03-Q4 | `average_picking_minutes` | Average Picking Time (Q4) | `AVG(imenitpick)` | minutes | Rata-rata durasi picking per office selama Q4. | approved candidate |
| PK-04-Q4 | `picking_rows` | Picking Workload Rows (Q4) | `COUNT(*)` | count | Jumlah baris operasional picking per office selama Q4. | contextual |
| UL-01-Q4 | `average_unloading_minutes` | Average Unloading Time (Q4) | `AVG(imenit)` | minutes | Rata-rata durasi unloading per office selama Q4. | approved candidate |
| UL-02-Q4 | `unloading_rows` | Unloading Events (Q4) | `COUNT(*)` | count | Jumlah baris/event unloading per office selama Q4. | contextual |
| XD-03-Q4 | `picking_rows_per_sales_line` | Picking Rows per Sales Line (Q4) | `picking_rows / NULLIF(sales_billing_lines, 0)` | ratio | Proxy intensitas workload picking dibanding jumlah billing line. Bukan productivity rate. | supporting |

### Period metadata

| Field | Value / meaning |
|---|---|
| `reporting_period` | `2024Q4` |
| `period_start_calmonth` | `202410` |
| `period_end_calmonth` | `202412` |
| `reporting_grain` | `sales_office_quarter` |

### Coverage validation

- Total sales offices: 52
- Offices with Sales: 52
- Offices with Picking: 23
- Offices with Unloading: 14
- Offices with full Sales + Picking + Unloading coverage: 14

### Caveat

- View ini adalah agregat Q4 dan tidak boleh digunakan untuk menjawab tren bulanan.
- Hanya 14 dari 52 office memiliki coverage lengkap untuk Sales, Picking, dan Unloading.
- `sales_billing_lines`, `picking_rows`, dan `unloading_rows` adalah jumlah baris, bukan document count unik.
- Versi bulanan perlu dibuat sebagai view terpisah dengan grain `calmonth + sales_off`.

---

## 6. Proposed Next Metric

KPI berikut belum tersedia pada view saat ini dan disarankan untuk fase selanjutnya:

| Proposed KPI | Formula | Purpose |
|---|---|---|
| Sell-Out to Sell-In Quantity Ratio | `SUM(b2b_bill_qty) / NULLIF(SUM(sales_bill_qty), 0)` | Indikator pergerakan unit/replenishment yang lebih kuat daripada value ratio |

Implementasi membutuhkan reconciliation view pada grain yang memiliki quantity Sell-In dan Sell-Out secara comparable.

---

## 7. OSSIE Mapping Guidance

Saat dipindahkan ke Apache Ossie:

- Gunakan `SO-07` sebagai KPI utama.
- Simpan `SO-07-INVERSE` sebagai metric pendukung.
- Jangan publish `LEGACY-SO-RATIO` pada `ai_context.synonyms`.
- Masukkan caveat shared-customer ke `ai_context.instructions`.
- Gunakan field Gold tanpa scaling tambahan.
- Definisikan allowed dimensions hanya `calmonth` dan `customer` untuk customer reconciliation.
- Gunakan `rpt_sap_material_month_semantic` untuk pertanyaan material/SKU lintas domain.
- Wajib enforce coverage flag sesuai domain yang diminta.
- Daftarkan `rpt_sales_office_performance_semantic` sebagai dataset Q4 tanpa time dimension bulanan.
- Gunakan primary key logical `[reporting_period, sales_office]`.
