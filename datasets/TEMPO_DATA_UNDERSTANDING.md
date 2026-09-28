# Tempo: Pemahaman Data & Daftar Klarifikasi

**Untuk:** Tim Tempo
**Dari:** Tim Cloudera Enterprise AI PoC
**Periode data yang kami terima:** Oktober – Desember 2024
**Sumber data:** SAP BW/ERP (export "Dynamic List Display") + sistem pendukung (SAT, Logistics)
**Status:** Partially confirmed. Jawaban awal Tempo tercatat di Section 9 (Sep 2025). Item #4 dan #9 masih pending.

**Tujuan dokumen ini:** Memastikan pemahaman kami terhadap data yang diterima sudah selaras sebelum lanjut ke desain datamart dan PoC AI.

**Lampiran terkait:**
- `TEMPO_KAMUS_DATA_AI.md` — kamus 9 domain + join playbook untuk agent AI
- `TEMPO_AI_ANALYTICS_PLAN.md` — arsitektur agent (router → query → preskriptif → semantic v2)
- `TEMPO_BUSINESS_QUESTIONS_CATALOG.md` — 15 pertanyaan × 9 dataset + query picking/unloading/promo
- `TEMPO_BUSINESS_QUESTIONS_CHART_INDEX.md` — chart wajib per ID pertanyaan (`chart_spec`)
- `assets/tempo-agent-orchestration-architecture.png` — diagram Master Agent Orchestration
- `TEMPO_FILE_MAPPING.md` — detail kolom per file (referensi teknis)
- `TEMPO_DATAMART_ERD.drawio` / `.png` — usulan relasi antar data (visual)
- `recording understanding/catatan meeting tempo.md` — catatan diskusi tim Tempo (promo, OOS, operasional)
- `TEMPO_F0B_DISPATCH.md` — checklist kirim follow-up Tempo
- `TEMPO_UAT_SESSION.md` — 20 pertanyaan UAT preskriptif (F5)
- `projects/tempo_scan_impala/agents/` — prompt Master + 9 domain agent Agent Studio

---

## 1. Ringkasan Pemahaman Kami

Kami menerima **21 file** (~2.9 GB, ~10 juta+ baris) yang mencakup **7 domain bisnis**:

| # | Domain | Pemahaman kami | Periode (verified) |
|---|--------|----------------|-------------------|
| 1 | **Sales (General Trade)** | Transaksi penjualan detail: qty, nilai, diskon, COGS | Okt – Des 2024 |
| 2 | **B2B Sales** | Penjualan channel B2B / Key Account | Okt – Des 2024 |
| 3 | **Service Level** | KPI pemenuhan order (DO vs PO, lead time) | Okt – Des 2024 |
| 4 | **Stock** | Posisi stok per material, plant, gudang | Okt – Des 2024 |
| 5 | **Logistics** | Operasional picking & unloading gudang | Okt – Des 2024 |
| 6 | **SAT (Field Audit)** | Data lapangan: Out of Stock & Promo di toko | OOS: Okt–Des; Promo: **Des saja** |
| 7 | **Reference** | Master UOM, mapping key figure, catatan data | Referensi (bukan transaksi) |

**Catatan:** Pemahaman di atas berdasarkan inspeksi struktural file. Definisi bisnis resmi masih menunggu konfirmasi Tempo (lihat Section 5–7).

---

## 2. Inventori File per Domain

### 2.1 Sales — Transaksi Penjualan (General Trade)

**Katalog field:** lihat `TEMPO_SALES_FIELD_CATALOG.md`.

| No | Nama File | Periode | Pemahaman Isi Data | Status Definisi |
|----|-----------|---------|-------------------|-----------------|
| S1 | `Sales 1-15 Oct 2024.txt` | 1–15 Okt 2024 | Penjualan paruh pertama Oktober | Sebagian: interpretasi SAP + file reference |
| S2 | `Sales 16-31 Oct 2024.txt` | 16–31 Okt 2024 | Penjualan paruh kedua Oktober | Sebagian |
| S3 | `Sales 1-15 Nov 2024.txt` | 1–15 Nov 2024 | Penjualan paruh pertama November (ada kolom harian) | Sebagian |
| S4 | `Sales 16-30 Nov 2024.txt` | 16–30 Nov 2024 | Penjualan paruh kedua November (ada kolom harian) | Sebagian |
| S5 | `Sales 1-15 Dec 2024.txt` | 1–15 Des 2024 | Penjualan paruh pertama Desember | Sebagian |
| S6 | `Sales 16-31 Dec 2024.txt` | 16–31 Des 2024 | Penjualan paruh kedua Desember (beberapa kolom rename) | Sebagian |

**Pemahaman granularitas:** 1 baris = kombinasi customer × material × sales office × periode (bulanan; November juga punya granularity harian via `0CALDAY`).

**Dimensi yang kami identifikasi:**
- Customer, Material, Sales Org / Office / Group
- Bill Type, Route, Sub-hub
- Bulan (November: juga per hari)

**Metrik yang kami identifikasi:**

| Kolom | Pemahaman kami (draft) | Definisi resmi dari Tempo |
|-------|------------------------|---------------------------|
| `0BILL_QTY` / `BILL_VAL` | Quantity & nilai penjualan billing | `[Perlu konfirmasi]` |
| `CN_AMT` / `CN_QTY` | Credit note (retur/koreksi) | `[Perlu konfirmasi]` |
| `DO_AMT` / `DO_QTY` | Delivery order amount & quantity | `[Perlu konfirmasi]` |
| `DO Amount` / `Net Sales` | Kolom pengganti di file Des 16–31 | `[Perlu konfirmasi]` — apakah sama dengan `DO_AMT` / `VV802`? |
| `DIS_*` (23 kolom) | Berbagai jenis diskon | `[Belum ada definisi]` |
| `ZCOST` | COGS (Cost of Goods Sold) | Ada di file reference |
| `ZIOKF0028–0033` | Custom key figures (cash discount, volume discount, dll.) | Sebagian ada di file reference |

**Temuan yang perlu diklarifikasi:**
- Nilai key figure perlu **÷ 100** saat dipakai (berdasarkan `Catatan terkait Data.xlsx`)
- Kolom tidak 100% konsisten antar periode: Nov punya `0CALDAY`, Des 16–31 rename beberapa kolom
- Sebagian kolom di-mask oleh SAP export (`...MATLGRP`, `...T_GROUP`, dll.)

---

### 2.2 B2B Sales — Penjualan Key Account

**Katalog field:** lihat `TEMPO_B2B_FIELD_CATALOG.md`.

| No | Nama File | Periode | Pemahaman Isi Data | Status Definisi |
|----|-----------|---------|-------------------|-----------------|
| B1 | `B2B 10.2024.txt` | Oktober 2024 | Penjualan B2B bulan Oktober | Sebagian |
| B2 | `B2B 11.2024.txt` | November 2024 | Penjualan B2B bulan November | Sebagian |
| B3 | `B2B 12.2024.txt` | Desember 2024 | Penjualan B2B bulan Desember | Sebagian |

**Pemahaman granularitas:** 1 baris = customer × material × sales office × bulan (12 kolom, lebih sederhana dari Sales general).

**Metrik:** `BILL_QTY`, `BILL_VAL`

**Pertanyaan kritis:**

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| B2B-1 | Apakah data B2B **sudah termasuk** di file Sales general, atau **terpisah/independen**? | |
| B2B-2 | Apakah boleh dijumlahkan B2B + Sales untuk total revenue, atau akan double-count? | |
| B2B-3 | Apa definisi `KA Group`, `Kode PLU`, dan kolom `...E_STORE` (masked)? | |

---

### 2.3 Service Level — KPI Pemenuhan Order

| No | Nama File | Periode | Pemahaman Isi Data | Status Definisi |
|----|-----------|---------|-------------------|-----------------|
| SL1 | `Service Level Oct - Dec 2024.txt` | Okt – Des 2024 | KPI service level: DO vs PO, lead time, NSP | Sebagian |

**Pemahaman granularitas:** 1 baris = material × sales office × customer group × bulan
**Volume verified:** Okt ~87K, Nov ~68K, Des ~68K baris

**Metrik yang kami identifikasi:**

| Kolom | Pemahaman kami (draft) | Definisi resmi dari Tempo |
|-------|------------------------|---------------------------|
| `DO_AMT` / `DO_QTY` | Delivery Order (sudah dikirim) | `[Perlu konfirmasi]` |
| `PO_AMT` / `PO_QTY` | Purchase Order (dipesan customer) | `[Perlu konfirmasi]` |
| `NSP` | Net Sales Price (?) | `[Perlu konfirmasi]` |
| `Lead = 4` | Lead time | `[Perlu konfirmasi]` — naming tidak standar |
| `ZIOKF0034–0069` (34 kolom) | Custom KPI service level | `[Belum ada definisi]` — tidak ada di file reference |

**Pertanyaan kritis:**

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| SL-1 | Apa **formula resmi fill rate / service level**? Apakah `DO_QTY / PO_QTY`? | |
| SL-2 | Apa definisi resmi `NSP` dan `Lead = 4`? | |
| SL-3 | Bisa share definisi `ZIOKF0034–0069`? (tidak ada di `Custom Key Figure Sales.xlsx`) | |
| SL-4 | Bagaimana join `cust_group` (Service Level) ke `customer` (Sales)? Ada mapping table? | |

---

### 2.4 Stock — Inventory

**Katalog Stock Tempo:** `TEMPO_STOCK_TEMPO_FIELD_CATALOG.md`.

| No | Nama File | Periode | Pemahaman Isi Data | Status Definisi |
|----|-----------|---------|-------------------|-----------------|
| ST1 | `Stock 10.2024.txt` | Oktober 2024 | Snapshot stok akhir Oktober | Sebagian |
| ST2 | `Stock 11.2024.txt` | November 2024 | Snapshot stok akhir November | Sebagian |
| ST3 | `Stock 12.2024.txt` | Desember 2024 | Snapshot stok akhir Desember | Sebagian |
| ST4 | `Stock SAT-IDM Monthly Okt-Des 24.xlsb` | Okt – Des 2024 (?) | Stok dari sistem SAT-IDM | `[Belum di-inspect]` |

**Pemahaman granularitas:** 1 baris = material × plant × storage location × bulan

**Metrik:** Consignment stock, Total stock, Stock value (sebagian kolom di-mask: `...CNSSTCK`, `...TOTSTCK`, `...VALSTCK`)

**Pertanyaan kritis:**

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| ST-1 | Apa beda Stock Tempo (ST1–ST3) vs Stock SAT-IDM (ST4)? | |
| ST-2 | Catatan "data yang tidak digunakan sudah dihapus" — data apa yang di-exclude? | |
| ST-3 | Apakah join stock harus pakai **plant + storage location** (composite key)? | |
| ST-4 | Bisa kirim versi lengkap kolom yang di-mask? | |

---

### 2.5 Logistics — Operasional Gudang

**Katalog field:** `TEMPO_LOGISTICS_FIELD_CATALOG.md`.

| No | Nama File | Periode | Pemahaman Isi Data | Status Definisi |
|----|-----------|---------|-------------------|-----------------|
| L1 | `Picking Okt - Des 24.xlsx` | Okt – Des 2024 | Proses picking: durasi, qty, status | `[Belum ada definisi]` |
| L2 | `Unloading Okt - Des 24.xlsx` | Okt – Des 2024 | Proses unloading: durasi, qty | `[Belum ada definisi]` |

**Catatan:** Data ini dari sistem logistics Tempo (bukan SAP BW export). Belum ada data dictionary.

**Pertanyaan:**

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| L-1 | Apakah data Logistics perlu dimasukkan scope PoC? | |
| L-2 | Bisa share definisi kolom `iMenitPick`, `Cycle`, `sStatus`, `LP`? | |

---

### 2.6 SAT — Data Audit Lapangan

| No | Nama File | Periode | Pemahaman Isi Data | Status Definisi |
|----|-----------|---------|-------------------|-----------------|
| SAT1 | `SAT OOS Okt - Des 2024.xlsx` | Okt – Des 2024 (harian) | Out of Stock di toko: tanggal, customer, material, stok akhir | Sebagian |
| SAT2 | `SAT Promo Des 24.xlsx` | **Desember 2024 saja** | Promo di lapangan: mekanisme, status program | Katalog: `TEMPO_SAT_PROMO_FIELD_CATALOG.md` |

**Volume verified SAT OOS:** Okt ~306K, Nov ~312K, Des ~282K baris (granularity harian)

**Pertanyaan:**

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| SAT-1 | SAT Promo kenapa cuma Desember? Apakah data Okt–Nov bisa disediakan? | |
| SAT-2 | Apa definisi `Stok_akhir`, `Mekanisme`, `Program_Status`? | |
| SAT-3 | Apakah OK aggregate OOS harian ke bulanan untuk join ke Sales? | |

---

## 3. Data Pendukung (Reference)

File kecil berikut membantu kami memahami istilah dan kode di data transaksi:

### 3.1 Base UOM (`Base UOM.XLSX`)

| Item | Detail |
|------|--------|
| **Isi** | Master satuan ukuran SAP (~381 UOM: KG, DUS, KAR, BOT, PCS, dll.) |
| **Dipakai untuk** | Interpretasi kolom `0BASE_UOM` di Sales, B2B, Stock, Service Level |
| **Status** | Lengkap untuk kebutuhan UOM lookup |
| **Pertanyaan** | Apakah ada UOM tambahan di luar file ini? |

### 3.2 Custom Key Figure Sales (`Custom Key Figure Sales.xlsx`)

| Kode | Deskripsi (dari file) | Ada di data transaksi? |
|------|----------------------|------------------------|
| ZIOKF0028 | Cash Discount Sales | Ya (Sales) |
| ZOKF0029 | Cash Discount Return | Ya (sebagai ZIOKF0029 di data) |
| ZOKF0030 | Disc. Principal F1 | Ya (sebagai ZIOKF0030) |
| ZOKF0031 | Disc. F5 Add Hoc | Ya (sebagai ZIOKF0031) |
| ZOKF0032 | Disc. Inv Volume | Ya (sebagai ZIOKF0032) |
| ZOKF0033 | Disc. CN Volume | Ya (sebagai ZIOKF0033) |
| ZIOCH0042 | Customer Number (Sales View) | Ya (Sales) |
| ZCOST | COGS Value | Ya (Sales) |

**Gap yang kami temukan:**

| Gap | Detail | Pertanyaan ke Tempo |
|-----|--------|---------------------|
| Naming inconsistency | File reference: `ZOKF0029`, data aktual: `ZIOKF0029` | Apakah ini field yang sama? |
| Field tanpa definisi | `ZDIS_D8`, `ZSUBHUB` ada di data Sales tapi tidak ada di file reference | Apa definisinya? |
| 23 kolom `DIS_*` | Ada di Sales, tidak ada definisi di file manapun | Bisa share data dictionary discount? |
| Service Level Z-fields | `ZIOKF0034–0069` (34 kolom) tidak ada di file reference | Bisa share definisinya? |

### 3.3 Catatan terkait Data (`Catatan terkait Data.xlsx`)

| No | Isi Catatan (dari file) | Pemahaman kami | Pertanyaan |
|----|------------------------|----------------|------------|
| 1 | "data sales jan-mar 2026–2034" + aturan key figure × 100 | Label tahun aneh, tapi aturan ×100 masuk akal | Apakah label "2026–2034" typo/placeholder? Aturan ×100 berlaku untuk file Okt–Des 2024? |
| 2 | Mapping key figure ZIOKF0028–0033, ZIOCH0042 | Kamus custom figures | Sudah selaras dengan `Custom Key Figure Sales.xlsx`? |
| 3 | "char MATLGRP pada Mar 2026: 3 char awal dari material group" | Aturan transform material group | Maksud "Mar 2026" apa? Berlaku untuk semua bulan Okt–Des 2024? |
| 4 | "data stock: data yang tidak digunakan sudah dihapus" | Stock sudah di-filter | Data apa saja yang di-exclude? |

---

## 4. Periode Data: Apakah Semua Sama?

**Jawaban singkat:** Mayoritas **Q4 2024 (Okt–Des)**, tapi ada perbedaan granularitas dan kelengkapan:

| Dataset | Periode | Granularitas | Catatan |
|---------|---------|--------------|---------|
| Sales (6 file) | Okt – Des 2024 | Bulanan; **Nov juga harian** | Des 16–31: kolom rename |
| B2B (3 file) | Okt – Des 2024 | Bulanan | Konsisten |
| Stock Tempo (3 file) | Okt – Des 2024 | Bulanan snapshot | Konsisten |
| Service Level (1 file) | Okt – Des 2024 | Bulanan | Verified per bulan |
| SAT OOS | Okt – Des 2024 | **Harian** | Perlu aggregate untuk join ke Sales |
| SAT Promo | **Des 2024 saja** | Harian | Tidak full quarter |
| Picking / Unloading | Okt – Des 2024 | Per transaksi | |
| Stock SAT-IDM | Okt – Des 2024 (?) | Belum di-inspect | |

```
         Okt 2024    Nov 2024    Des 2024
Sales    ████████    ████████*   ████████   (* Nov = +daily)
B2B      ████████    ████████    ████████
Stock    ████████    ████████    ████████
Svc Lvl  ████████    ████████    ████████
SAT OOS  ████████    ████████    ████████   (daily)
SAT Promo                     ████          (Des only)
```

**Pertanyaan:**

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| P-1 | Apakah Okt–Des 2024 representatif untuk PoC, atau perlu periode lain? | |
| P-2 | Kenapa Nov punya granularity harian (`0CALDAY`) tapi bulan lain tidak? | |
| P-3 | Apakah ada data yang sengaja di-exclude dari export? | |

---

## 5. Gap Data Dictionary

Ringkasan cakupan definisi field yang kami miliki saat ini:

| Kategori | Jumlah kolom (perkiraan) | Punya definisi resmi? | Sumber definisi |
|----------|--------------------------|----------------------|-----------------|
| SAP standard (`0*`) | ~16 per file Sales | Interpretasi SAP standard | Naming convention SAP |
| Custom Z-fields (Sales) | 10 | 3 resmi, 7 belum | `Custom Key Figure Sales.xlsx` |
| Discount (`DIS_*`) | 23 | **Tidak ada** | — |
| Service Level Z-fields | 34 | **Tidak ada** | — |
| Metrik utama (BILL_VAL, DO_AMT, dll.) | ~10 | **Belum dikonfirmasi** | Interpretasi SAP |
| Kolom di-mask (`...*`) | 4+ | **Tidak ada** | — |
| Logistics & SAT | Semua | **Tidak ada** | — |

**Mohon bantuan Tempo:** Data dictionary lengkap (field name, definisi bisnis, formula, contoh nilai) akan sangat membantu kami mendefinisikan metrik KPI dan semantic layer untuk PoC AI.

---

## 6. Usulan Relasi Antar Data (Perlu Konfirmasi)

Berikut pemahaman kami tentang bagaimana data-data ini bisa dihubungkan. Mohon koreksi jika ada relasi yang salah atau join key yang kurang tepat.

### 6.1 Join Keys

| Entitas | Key di data | Muncul di file |
|---------|-------------|----------------|
| Customer | `0CUSTOMER` / `Cust Id` / `cust_id` | Sales, B2B, Picking, SAT |
| Material | `0MATERIAL` / `Material_code` / `PLU` | Sales, B2B, Stock, Service Level, SAT |
| Sales Office | `0SALES_OFF` / `sales_office` | Sales, B2B, Service Level, Picking, Unloading |
| Bulan | `0CALMONTH` / `TGL_DCP` | Semua (kecuali Reference) |
| Plant / Gudang | `Plant` / `0STOR_LOC` | Stock saja |

### 6.2 Relasi antar Domain (usulan)

| Dari | Ke | Join Key | Catatan / Risiko |
|------|----|----------|------------------|
| Sales | B2B | customer + material + sales_office + bulan | `[Perlu konfirmasi]` — apakah overlap? |
| Sales | Stock | material + bulan | Grain berbeda (customer vs plant) |
| Sales | Service Level | material + sales_office + bulan | Service Level pakai `cust_group`, bukan `customer` |
| Sales | SAT OOS | customer + material + bulan | OOS harian, perlu aggregate ke bulanan |
| Stock | SAT OOS | material | Cross-check availability vs lapangan |
| Sales | Picking | sales_office + customer (ship-to) | Logistics opsional |

**Visual ERD:** Lihat `TEMPO_DATAMART_ERD.drawio` / `.png` untuk diagram relasi lengkap.

**Pertanyaan join governance:**

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| J-1 | Apakah composite key `sales_org + sales_office` harus dipakai bersama saat join? | |
| J-2 | Apakah composite key `plant + storage_location` harus dipakai bersama? | |
| J-3 | Apakah aggregate OOS harian ke bulanan OK untuk analisis cross-domain? | |
| J-4 | Bagaimana mapping `cust_group` (Service Level) ↔ `customer` (Sales)? | |

---

## 7. Usulan Metrik Bisnis (Perlu Konfirmasi Formula Resmi)

Berikut metrik yang kami identifikasi dari data. **Formula di bawah adalah dugaan kami**, belum final.

### 7.1 Sales & B2B

| Metrik | Formula usulan kami | Kolom sumber | Pertanyaan ke Tempo |
|--------|---------------------|--------------|---------------------|
| **Net Revenue** | `SUM(BILL_VAL)` | Sales, B2B | Apakah `BILL_VAL` = official revenue? Atau pakai `Net Sales` / `VV802`? |
| **Delivery Value** | `SUM(DO_AMT)` | Sales | Beda apa dengan BILL_VAL? |
| **Credit Note Rate** | `SUM(CN_AMT) / SUM(BILL_VAL)` | Sales | Apakah formula ini benar? |
| **Gross Margin** | `(SUM(BILL_VAL) - SUM(ZCOST)) / SUM(BILL_VAL)` | Sales | Apa formula resmi margin di Tempo? |
| **Total Discount** | `SUM(DIS_*) + SUM(ZIOKF0028–0033)` | Sales | Kolom discount mana saja yang masuk perhitungan? |
| **B2B Revenue** | `SUM(BILL_VAL)` | B2B | Boleh dijumlahkan dengan Sales general? |

### 7.2 Service Level

| Metrik | Formula usulan kami | Kolom sumber | Pertanyaan ke Tempo |
|--------|---------------------|--------------|---------------------|
| **Fill Rate** | `SUM(DO_QTY) / SUM(PO_QTY)` | Service Level | Apa formula resmi fill rate? |
| **Lead Time** | `AVG(Lead = 4)` | Service Level | Apa definisi & satuan lead time? |
| **NSP** | — | Service Level | Apa definisi NSP? |

### 7.3 Stock

| Metrik | Formula usulan kami | Kolom sumber | Pertanyaan ke Tempo |
|--------|---------------------|--------------|---------------------|
| **Stock Coverage** | `Stock Qty / Avg Monthly Sales Qty` | Stock + Sales | Apakah formula ini relevan? |
| **Stock Value** | `SUM(...VALSTCK)` | Stock | Kolom masked, perlu versi lengkap |

### 7.4 SAT (Field Audit)

| Metrik | Formula usulan kami | Kolom sumber | Pertanyaan ke Tempo |
|--------|---------------------|--------------|---------------------|
| **OOS Rate** | `COUNT(stok_akhir = 0) / COUNT(*)` | SAT OOS | Apa definisi OOS di Tempo? |
| **Promo Coverage** | `COUNT(Program_Status = 'X') / COUNT(*)` | SAT Promo | Apa arti status program? |

---

## 8. Scope PoC: Data yang Kami Usulkan Dipakai

Berdasarkan pemahaman kami, berikut prioritas penggunaan data untuk PoC. **Mohon konfirmasi apakah scope ini sesuai harapan Tempo.**

| Prioritas | Dataset | Alasan | Usulan |
|-----------|---------|--------|--------|
| **Core** | Sales, B2B, Stock | Revenue, channel, availability | Masuk scope PoC |
| **Enrichment** | Service Level, SAT OOS | Fill rate, retail execution | Masuk scope PoC |
| **Reference** | UOM, Key Figure, Catatan | Lookup & transform rules | Masuk scope PoC |
| **Opsional** | Picking, Unloading | Logistics efficiency | Fase 2? |
| **Incomplete** | SAT Promo (Des saja) | Promo analysis | Out of scope fase 1? |
| **TBC** | Stock SAT-IDM (.xlsb) | Belum di-inspect | Perlu penjelasan dari Tempo |

---

## 9. Jawaban Klarifikasi Tempo (10 Pertanyaan)

> **File lengkap:** `TEMPO_KLARIFIKASI_JAWABAN.md`
> **Pending:** #4 (custom field Z*), #9 (key figure ÷ 100, konfirmasi Pak Gunawan)

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| 1 | **Scope PoC:** Domain/table mana yang difokuskan? Join key, metrik/KPI, formula resmi? ERD dari sisi Tempo? | Semua table punya context bisnis masing-masing, dan beberapa data saling terkait (misalnya kode material, kode customer). Tempo **tidak menyiapkan ERD**. Boleh share draft ERD kami untuk feedback. |
| 2 | **Data dictionary:** Apakah tersedia? | **Tidak ada.** |
| 3 | **Catatan terkait Data.xlsx:** Tulisan "data sales jan-mar 2026–2034", apa maksudnya? | Catatan **masih relevan** untuk diterapkan ke data sales **Okt–Des 2024**. |
| 4 | **Custom field Z\*:** Definisi lengkap field custom, koreksi kolom `0*` jika beda dari SAP standard. | *(Belum dijawab)* |
| 5 | **Stock:** Beda `Stock*.txt` vs `Stock SAT-IDM*.xlsb`? Mana untuk PoC? | **Stock Tempo** = posisi stok di gudang/cabang milik Tempo. **Stock SAT-IDM** = stok produk Tempo di Dist.Center/Outlet milik Alfamart dan Indomaret. |
| 6 | **SAT:** Promo kenapa cuma Des? Okt–Nov bisa disediakan? OOS harian boleh di-aggregate ke bulanan? | Data promo **memang hanya Desember**. **Bebas** mengolah data dengan fungsi aggregate dll. |
| 7 | **Sales vs B2B:** Kenapa dipisah? Overlap atau terpisah? | **Sales** = penjualan Tempo ke semua customer (**Sell In**). **B2B** = penjualan Alfamart & Indomaret ke end consumer (**Sell Out**). Bukan overlap, context bisnis berbeda. *Catatan internal: usulan report Sell In vs Sell Out, verify ke data aktual dulu.* |
| 8 | **Revenue resmi:** `BILL_VAL`, `Net Sales`/`VV802`, atau `DO Amount`/`DO_AMT`? | Pakai **Bill Value (Gross Sales)**. |
| 9 | **Key figure ÷ 100:** Benar harus dibagi 100? Kolom mana? Berlaku Okt–Des 2024? | **Pak Gunawan** bisa berikan konfirmasi. *(Pending)* |
| 10 | **Master data tambahan:** Customer, material, plant, dll.? | **Tidak ada.** |

### Implikasi untuk datamart (dari jawaban di atas)

| Temuan | Impact ke PoC |
|--------|---------------|
| Sales = Sell In, B2B = Sell Out | **Jangan double-count** revenue. Analisis terpisah. Usulan report + **forecasting use case**: bandingkan Sell In vs Sell Out, gap jadi sinyal forecast demand modern trade (verify data dulu). |
| Stock Tempo vs SAT-IDM | Dua lensa berbeda: stok internal Tempo vs stok di outlet modern trade. |
| Revenue = `BILL_VAL` | Official metric untuk dashboard/AI: Gross Sales via Bill Value. |
| Tidak ada data dictionary & master data | Dim tetap kode saja. PoC fokus analisis numerik, bukan reporting dengan label nama. |
| Catatan file relevan untuk Okt–Des 2024 | Terapkan aturan transformasi (termasuk key figure ÷ 100 setelah konfirmasi #9). |
| Aggregate SAT OOS OK | Boleh agg harian ke bulanan untuk join ke Sales. |

---

## 10. Daftar Klarifikasi Lengkap (Referensi)

Mohon bantu jawab pertanyaan-pertanyaan berikut. Bisa langsung isi kolom "Jawaban Tempo" atau respon terpisah.

### A. Scope & Tujuan Bisnis

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| A1 | Use case utama PoC/datamart apa? (sales performance, margin, stock, service level, retail execution, dll.) | |
| A2 | Audience datamart siapa? (sales team, supply chain, management, field team) | |
| A3 | Apakah scope 5 domain core (Sales, B2B, Stock, Service Level, SAT OOS) sudah sesuai? | |

### B. Definisi Data & Data Dictionary

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| B1 | Apa beda Sales (general) vs B2B? Overlap atau terpisah? | |
| B2 | Mana official revenue figure: `BILL_VAL`, `Net Sales`/`VV802`, atau `DO Amount`/`DO_AMT`? | |
| B3 | Apa formula resmi gross margin? | |
| B4 | Apa formula resmi fill rate / service level? | |
| B5 | Bisa share data dictionary lengkap untuk kolom `DIS_*` (23 kolom discount)? | |
| B6 | Bisa share definisi `ZIOKF0034–0069` (Service Level custom KPI)? | |
| B7 | Custom key figures (ZIOKF0028–0033): apakah semua masih dipakai? Ada yang deprecated? | |
| B8 | Kolom di-mask (`...E_STORE`, `...MATLGRP`, dll.): bisa kirim versi lengkap? | |
| B9 | Stock SAT-IDM (.xlsb): apa isinya? Beda apa dengan Stock Tempo? | |

### C. Data Quality & Transformasi

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| C1 | Konfirmasi: nilai key figure memang harus ÷ 100? Berlaku Okt–Des 2024? | |
| C2 | Kolom mana saja yang kena aturan ÷ 100? Cuma ZIOKF + ZCOST, atau termasuk DIS_*? | |
| C3 | Label "jan-mar 2026–2034" di Catatan terkait Data: maksudnya apa? | |
| C4 | "char MATLGRP pada Mar 2026": typo atau fiscal period SAP? | |
| C5 | Kenapa Nov punya `0CALDAY` tapi bulan lain tidak? | |
| C6 | Des 16–31 rename kolom (`DO Amount`, `Net Sales`): mapping ke kolom lama? | |
| C7 | Data stock: "yang tidak digunakan sudah dihapus" — data apa yang di-exclude? | |

### D. Relasi, Join & Governance

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| D1 | Composite key `sales_org + sales_office`: harus dipakai bersama? | |
| D2 | Composite key `plant + storage_location`: harus dipakai bersama? | |
| D3 | OOS harian → aggregate ke bulanan OK untuk join ke Sales? | |
| D4 | Mapping `cust_group` ↔ `customer` untuk join Service Level ke Sales? | |
| D5 | Apakah ada hierarchy yang perlu di-support? (Sales Org → Office → Group, dll.) | |
| D6 | Apakah ada requirement access control? (role-based per region/office) | |

### E. Kelengkapan & Master Data

| # | Pertanyaan | Jawaban Tempo |
|---|-----------|---------------|
| E1 | Apakah ada master data terpisah? (Customer name, Material name, Sales Office hierarchy) | |
| E2 | Apakah Okt–Des 2024 representatif, atau perlu periode lain? | |
| E3 | SAT Promo Okt–Nov: bisa disediakan? | |
| E4 | Seberapa sering data di-update di production? (refresh schedule) | |

---

## 11. Langkah Selanjutnya

| Step | Action | PIC | Status |
|------|--------|-----|--------|
| 1 | Review dokumen ini | Tim Tempo + Tim Cloudera | ✅ Partial |
| 2 | Jawab 10 pertanyaan klarifikasi (Section 9) | Tim Tempo | ⬜ 8/10 answered |
| 3 | Konfirmasi #4 (Z*) dan #9 (÷ 100) via Pak Gunawan | Tim Tempo | ⬜ Pending |
| 4 | Review draft ERD kami | Tim Tempo | ⬜ Pending |
| 5 | Finalize scope & metrik KPI | Bersama | ⬜ |
| 6 | Lanjut desain datamart & PoC AI | Tim Cloudera | ⬜ |

---

*Dokumen ini disusun dari analisis struktural file di folder data MTPL. Tidak ada nilai data sensitif yang ditampilkan. Mohon koreksi jika ada pemahaman yang keliru.*
