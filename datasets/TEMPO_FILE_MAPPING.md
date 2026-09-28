# Tempo: Mapping File ke Definisi Data

Cara baca dokumen ini: **mulai dari atas**, pilih domain yang mau dipahami, lalu lihat file-nya satu per satu.

```
datasets/MTPL/
```

---

## Konvensi penamaan variabel (SAP)

Sebagian besar file TXT di dataset ini berasal dari export **SAP BW** (Business Warehouse) dengan format "Dynamic List Display". Penjelasan variabel/kolom di dokumen ini mengacu pada **standar penamaan SAP**, kecuali disebutkan otherwise.

| Prefix / Pola | Tipe di SAP | Contoh | Keterangan |
|---------------|-------------|--------|------------|
| `0` + UPPERCASE | **InfoObject standar SAP** | `0MATERIAL`, `0CUSTOMER`, `0CALMONTH` | Field bawaan SAP BW. Angka `0` di depan = standard InfoObject name. |
| `Z` + UPPERCASE | **Custom field Tempo** | `ZIOKF0028`, `ZCOST`, `ZIOCH0042` | Key figure/karakteristik custom yang didefinisikan Tempo di SAP. Lihat file R2 untuk mapping lengkap. |
| UPPERCASE tanpa prefix | **Key figure / alias query** | `BILL_VAL`, `DO_AMT`, `CN_QTY` | Nama key figure di report SAP BW. Umumnya terhubung ke InfoObject atau custom figure di backend. |
| `DIS_*`, `DISC*` | **Key figure diskon** | `DIS_A`, `DISCD12`, `DISCF2` | Custom discount figures di modul SD (Sales & Distribution). |
| `...` di awal nama | **Kolom di-mask** | `...E_STORE`, `...TOTSTCK` | SAP export menyembunyikan sebagian nama/info field. Perlu konfirmasi ke Tempo untuk versi lengkap. |
| lowercase / mixed case | **Bukan SAP BW export** | `sales_office`, `TGL_DCP` | Dari sistem lain (logistics, SAT). Definisi tidak mengacu ke SAP standard. |

**Sumber referensi definisi:**

| Prioritas | Sumber | Dipakai untuk |
|-----------|--------|---------------|
| 1 | SAP standard InfoObject | Field prefix `0` (Material, Customer, Calendar, Sales Org, dll.) |
| 2 | `Custom Key Figure Sales.xlsx` (R2) | Field prefix `Z` dan key figure custom Tempo |
| 3 | `Catatan terkait Data.xlsx` (R3) | Anomali, transformasi, dan catatan khusus Tempo |
| 4 | `Base UOM.XLSX` (R1) | Field `0BASE_UOM` dan satuan ukuran |

> Definisi di bawah ini adalah interpretasi berdasarkan **SAP standard naming**. Untuk custom field (`Z*`) dan key figure spesifik Tempo, **wajib dikonfirmasi ke customer** sebelum dipakai di datamart.

---

## Cara mulai pahami (urutan disarankan)

| Step | Mulai dari | Kenapa |
|------|------------|--------|
| 1 | **Reference** (3 file kecil) | Pahami istilah & kode SAP dulu |
| 2 | **Sales** (6 file) | Data inti penjualan |
| 3 | **B2B** (3 file) | Penjualan channel khusus |
| 4 | **Stock** (4 file) | Stok barang |
| 5 | **Service Level** (1 file) | KPI pemenuhan order |
| 6 | **Logistics** (2 file) | Operasional gudang |
| 7 | **SAT** (2 file) | Data audit lapangan |

---

## 1. Reference - Baca ini dulu

File kecil, isinya kamus/penjelasan. **Bukan transaksi.**

| No | Nama File | Lokasi | Data Apa Ini? | Isi Singkat |
|----|-----------|--------|---------------|-------------|
| R1 | `Base UOM.XLSX` | `MTPL/` | **Master satuan ukuran** | Daftar UOM SAP: KG, DUS, KAR, BOT, PCS, dll. |
| R2 | `Custom Key Figure Sales.xlsx` | `MTPL/` | **Kamus kode metrik sales** | Mapping kode SAP (ZIOKF0028, ZCOST, dll.) → nama bisnis (Cash Discount, COGS, dll.) |
| R3 | `Catatan terkait Data.xlsx` | `MTPL/` | **Catatan dari Tempo** | Penjelasan anomali data: key figure ×100, kolom yang diubah, dll. |

**Kapan dipakai:** Saat baca file Sales/Service Level dan bingung arti kolom `ZIOKF00xx` atau `DIS_xx`.

---

## 2. Sales - Transaksi Penjualan (General Trade)

**Katalog field lengkap:** `TEMPO_SALES_FIELD_CATALOG.md` (definisi per kolom, status konfirmasi Tempo, caveat periode).

**Definisi:** Detail transaksi billing/penjualan dari SAP BW.
**Satu baris =** 1 kombinasi customer × produk × sales office × periode.
**Format:** TXT, tab-delimited, skip 3 baris header.

| No | Nama File | Lokasi | Periode | Data Apa Ini? |
|----|-----------|--------|---------|---------------|
| S1 | `Sales 1-15 Oct 2024.txt` | `MTPL/Oct - Dec 2024 New/` | 1–15 Oktober 2024 | Penjualan paruh pertama Oktober |
| S2 | `Sales 16-31 Oct 2024.txt` | `MTPL/Oct - Dec 2024 New/` | 16–31 Oktober 2024 | Penjualan paruh kedua Oktober |
| S3 | `Sales 1-15 Nov 2024.txt` | `MTPL/Oct - Dec 2024 New/` | 1–15 November 2024 | Penjualan paruh pertama November |
| S4 | `Sales 16-30 Nov 2024.txt` | `MTPL/Oct - Dec 2024 New/` | 16–30 November 2024 | Penjualan paruh kedua November |
| S5 | `Sales 1-15 Dec 2024.txt` | `MTPL/Oct - Dec 2024 New/` | 1–15 Desember 2024 | Penjualan paruh pertama Desember |
| S6 | `Sales 16-31 Dec 2024.txt` | `MTPL/Oct - Dec 2024 New/` | 16–31 Desember 2024 | Penjualan paruh kedua Desember |

**Kolom penting** (based on SAP BW standard):

| Kolom | Tipe SAP | Definisi (SAP Standard) |
|-------|----------|-------------------------|
| `0CUSTOMER` | InfoObject | Sold-to / Bill-to party. ID customer di SAP SD. |
| `0MATERIAL` | InfoObject | Material master number. ID produk/barang. |
| `0SALESORG` | InfoObject | Sales Organization. Unit penjualan level org. |
| `0SALES_OFF` | InfoObject | Sales Office. Cabang/area penjualan. |
| `0SALES_GRP` | InfoObject | Sales Group. Tim sales yang handle customer. |
| `0SOLD_TO` | InfoObject | Sold-to party. Pihak yang menerima barang. |
| `0CALMONTH` | InfoObject | Calendar month (format YYYYMM). |
| `0CALMONTH2` | InfoObject | Calendar month variant. |
| `0CALDAY` | InfoObject | Calendar day (hanya ada di file Nov). |
| `0FISCPER` | InfoObject | Fiscal period. |
| `0BILL_TYPE` | InfoObject | Billing document type (F2, G2, dll.) |
| `0DOC_TYPE` | InfoObject | Sales document type (OR, RE, dll.) |
| `0CUST_GRP3` | InfoObject | Customer group 3 (segmentasi customer). |
| `0BASE_UOM` | InfoObject | Base unit of measure. Lihat file R1. |
| `0BILL_QTY` | Key figure | Billing quantity dalam base UOM. |
| `BILL_VAL` | Key figure | Billing value / net value dari billing doc. |
| `CN_AMT` / `CN_QTY` | Key figure | Credit note amount & quantity (retur/koreksi). |
| `DO_AMT` / `DO_QTY` | Key figure | Delivery order amount & quantity. |
| `DIS_*` | Key figure | Discount figures (custom di modul SD Tempo). |
| `ZCOST` | Custom (Z) | COGS value. Custom key figure Tempo. |
| `ZIOKF0028–0033` | Custom (Z) | Custom sales metrics Tempo. Lihat file R2. |
| `ZIOCH0042` | Custom (Z) | Customer Number (Sales View). |
| `ZSUBHUB` | Custom (Z) | Sub-hub / sub-distribution point. |
| `Route List` | Custom | Route pengiriman (non-standard naming). |

**Catatan:** File di-split per paruh bulan karena ukuran besar (150–490 MB per file).

---

## 3. B2B Sales - Penjualan Key Account

**Katalog field lengkap:** `TEMPO_B2B_FIELD_CATALOG.md` (definisi per kolom, 13 field, contoh nilai).

**Definisi:** Penjualan khusus channel B2B / modern trade / Key Account.
**Satu baris =** 1 kombinasi customer × produk × sales office × bulan.
**Format:** TXT, tab-delimited, skip 3 baris header.

| No | Nama File | Lokasi | Periode | Data Apa Ini? |
|----|-----------|--------|---------|---------------|
| B1 | `B2B 10.2024.txt` | `MTPL/B2B Oct - Dec 2024/` | Oktober 2024 | Penjualan B2B bulan Oktober |
| B2 | `B2B 11.2024.txt` | `MTPL/B2B Oct - Dec 2024/` | November 2024 | Penjualan B2B bulan November |
| B3 | `B2B 12.2024.txt` | `MTPL/B2B Oct - Dec 2024/` | Desember 2024 | Penjualan B2B bulan Desember |

**Kolom penting** (based on SAP BW standard):

| Kolom | Tipe SAP | Definisi (SAP Standard) |
|-------|----------|-------------------------|
| `0CUSTOMER` | InfoObject | Customer ID (SAP SD). |
| `0MATERIAL` | InfoObject | Material master number. |
| `0SALES_OFF` | InfoObject | Sales Office. |
| `0CALMONTH` | InfoObject | Calendar month (YYYYMM). |
| `0BASE_UOM` | InfoObject | Base unit of measure. |
| `0BILL_QTY` | Key figure | Billing quantity. |
| `BILL_VAL` | Key figure | Billing value. |
| `BRANCH` | Custom | Cabang (non-standard, perlu konfirmasi mapping ke SAP). |
| `...E_STORE` | Masked | E-store identifier (nama kolom di-mask SAP). |
| `KA Group` | Custom | Key Account group (segmentasi B2B). |
| `Kode PLU` | Custom | Price Look-Up code, kode produk di retail/modern trade. |

**Bedanya dengan Sales (S1–S6):** Lebih sederhana (12 kolom vs 60), fokus channel B2B. Perlu konfirmasi ke Tempo: apakah overlap dengan Sales atau terpisah.

---

## 4. Stock - Posisi Inventory

**Definisi:** Snapshot stok barang per gudang/plant.
**Satu baris =** 1 kombinasi material × plant × storage location × bulan.

### 4a. Stock Tempo (SAP export)

**Katalog field:** `TEMPO_STOCK_TEMPO_FIELD_CATALOG.md` (18 kolom, plant + stor_loc, masked stock figures).

| No | Nama File | Lokasi | Periode | Data Apa Ini? |
|----|-----------|--------|---------|---------------|
| ST1 | `Stock 10.2024.txt` | `MTPL/Stock Tempo Oct-Dec 2024/` | Oktober 2024 | Posisi stok akhir Oktober |
| ST2 | `Stock 11.2024.txt` | `MTPL/Stock Tempo Oct-Dec 2024/` | November 2024 | Posisi stok akhir November |
| ST3 | `Stock 12.2024.txt` | `MTPL/Stock Tempo Oct-Dec 2024/` | Desember 2024 | Posisi stok akhir Desember |

**Kolom penting** (based on SAP BW / MM standard):

| Kolom | Tipe SAP | Definisi (SAP Standard) |
|-------|----------|-------------------------|
| `0MATERIAL` | InfoObject | Material master number. |
| `0PRODUCT` | InfoObject | Product number (alternatif material di SAP). |
| `Plant` | InfoObject (0PLANT) | Plant / manufacturing site / gudang. |
| `0STOR_LOC` | InfoObject | Storage location dalam plant. |
| `0STOCKCAT` | InfoObject | Stock category (unrestricted, quality inspection, dll.) |
| `0STOCKTYPE` | InfoObject | Stock type. |
| `0VENDOR` / `Vendor` | InfoObject | Vendor for consignment stock. |
| `0CALMONTH` | InfoObject | Calendar month snapshot. |
| `0UPD_DATE` | InfoObject | Last update date of stock record. |
| `0BASE_UOM` | InfoObject | Base unit of measure. |
| `0RECORDTP` | InfoObject | Record type (indicator jenis record stok). |
| `...CNSSTCK` | Key figure (masked) | Consignment stock quantity. |
| `...TOTSTCK` | Key figure (masked) | Total stock quantity. |
| `...VALSTCK` | Key figure (masked) | Total stock value. |

### 4b. Stock SAT-IDM

**Katalog field:** `TEMPO_STOCK_SAT_IDM_FIELD_CATALOG.md` (DC vs store stock, PLU, contoh screenshot).

| No | Nama File | Lokasi | Periode | Data Apa Ini? |
|----|-----------|--------|---------|---------------|
| ST4 | `Stock SAT-IDM Monthly Okt-Des 24.xlsb` | `MTPL/` | Okt–Des 2024 | Stok produk Tempo di **DC & outlet** Alfamart/Indomaret (bukan gudang Tempo) |

**Catatan:** Bukan file SAT OOS/Promo. Inspect penuh `.xlsb` di repo optional; kolom `di...` masih pending definisi Tempo.

---

## 5. Service Level - KPI Pemenuhan Order

**Katalog field lengkap:** `TEMPO_SERVICE_LEVEL_FIELD_CATALOG.md` (50 kolom, PO/DO, ZIOKF0034–0069).

**Definisi:** Seberapa baik Tempo memenuhi order dari customer (fill rate, lead time).
**Satu baris =** 1 kombinasi material × sales office × customer group × bulan.

| No | Nama File | Lokasi | Periode | Data Apa Ini? |
|----|-----------|--------|---------|---------------|
| SL1 | `Service Level Oct - Dec 2024.txt` | `MTPL/` | Okt–Des 2024 | KPI service level (DO vs PO, lead time, NSP) |

**Kolom penting** (based on SAP BW standard):

| Kolom | Tipe SAP | Definisi (SAP Standard) |
|-------|----------|-------------------------|
| `0MATERIAL` | InfoObject | Material master number. |
| `0SALESORG` | InfoObject | Sales Organization. |
| `0SALES_OFF` | InfoObject | Sales Office. |
| `0CUST_GRP3` | InfoObject | Customer group 3. |
| `0CALMONTH` | InfoObject | Calendar month. |
| `0CALYEAR` | InfoObject | Calendar year. |
| `0BASE_UOM` | InfoObject | Base unit of measure. |
| `0AF_CGR6` | InfoObject | Characteristic group (perlu konfirmasi ke Tempo). |
| `DO_AMT` / `DO_QTY` | Key figure | Delivery Order amount & quantity (sudah dikirim). |
| `PO_AMT` / `PO_QTY` | Key figure | Purchase Order amount & quantity (dipesan customer). |
| `NSP` | Key figure | Net Sales Price (perlu konfirmasi definisi exact ke Tempo). |
| `Lead = 4` | Key figure | Lead time (custom naming, perlu konfirmasi). |
| `ZIOKF0034–0069` | Custom (Z) | Custom service level KPI Tempo. Lihat file R2/R3. |

**Analogi sederhana:** Customer pesan 100 unit (PO), Tempo kirim 85 unit (DO) → service level = 85%.

---

## 6. Logistics - Operasional Gudang

**Katalog field:** `TEMPO_LOGISTICS_FIELD_CATALOG.md` (Picking 13 kolom, Unloading 8 kolom).

**Definisi:** Data proses fisik di gudang, ambil barang (picking) dan bongkar barang (unloading).

| No | Nama File | Lokasi | Periode | Data Apa Ini? |
|----|-----------|--------|---------|---------------|
| L1 | `Picking Okt - Des 24.xlsx` | `MTPL/` | Okt–Des 2024 | Proses picking: ambil barang dari rak untuk order |
| L2 | `Unloading Okt - Des 24.xlsx` | `MTPL/` | Okt–Des 2024 | Proses unloading: bongkar barang dari truk |

**Kolom Picking (L1)** - *bukan SAP BW export, dari sistem logistics Tempo:*

| Kolom | Tipe | Definisi |
|-------|------|----------|
| `sales_office` | Custom | Cabang. Relates to SAP `0SALES_OFF`. |
| `ship_to_party` | Custom | Tujuan kirim. Relates to SAP `0CUSTOMER` / ship-to party. |
| `customer_subgroup_code` | Custom | Sub-segment customer. |
| `delivery_no` | Custom | Nomor delivery document. Relates to SAP delivery doc. |
| `QtyMat` / `QtyTot` / `QtyCart` | Metric | Quantity: material / total / carton. |
| `iMenitPick` | Metric | Durasi picking dalam menit. |
| `Cycle` | Custom | Siklus picking. |
| `sStatus` | Custom | Status proses picking. |
| `LP` | Custom | Loading point (perlu konfirmasi). |

**Kolom Unloading (L2)** - *bukan SAP BW export, dari sistem logistics Tempo:*

| Kolom | Tipe | Definisi |
|-------|------|----------|
| `sales_office` | Custom | Cabang. Relates to SAP `0SALES_OFF`. |
| `document_number` | Custom | Nomor dokumen unloading. |
| `iMenit` | Metric | Durasi unloading dalam menit. |
| `QtyDN` / `QtyMat` / `QtyTot` | Metric | Quantity: delivery note / material / total. |

---

## 7. SAT - Data Audit Lapangan

**Katalog SAT OOS:** `TEMPO_SAT_OOS_FIELD_CATALOG.md` (6 kolom, harian Okt–Des).
**Katalog SAT Promo:** `TEMPO_SAT_PROMO_FIELD_CATALOG.md` (6 kolom, **Des 2024 saja**).

**Definisi:** Data dari tim Sales Audit Team (SAT) yang survei toko di lapangan.
**Bukan dari SAP**, dari sistem audit terpisah.

| No | Nama File | Lokasi | Periode | Data Apa Ini? |
|----|-----------|--------|---------|---------------|
| SAT1 | `SAT OOS Okt - Des 2024.xlsx` | `MTPL/` | Okt–Des 2024 | Out of Stock, produk kosong di rak toko |
| SAT2 | `SAT Promo Des 24.xlsx` | `MTPL/` | Des 2024 saja | Promo yang berjalan di toko |

**Kolom SAT OOS (SAT1)** - *bukan SAP, dari sistem Sales Audit Team (SAT):*

| Kolom | Tipe | Definisi | Relasi ke SAP |
|-------|------|----------|---------------|
| `TGL_DCP` | Date | Tanggal survey/audit di lapangan. | Relates to calendar |
| `Cust Id` / `Cust Code` | ID | ID customer/toko di sistem SAT. | Maps to `0CUSTOMER` |
| `Material_code` / `PLU` | ID | Kode material / PLU produk. | Maps to `0MATERIAL` |
| `Stok_akhir` | Metric | Stok terakhir di rak toko. 0 = Out of Stock. | - |

**Kolom SAT Promo (SAT2)** - *bukan SAP, dari sistem Sales Audit Team (SAT):*

| Kolom | Tipe | Definisi | Relasi ke SAP |
|-------|------|----------|---------------|
| `TGL_DCP` | Date | Tanggal survey promo. | Relates to calendar |
| `cust_id` / `cust_code` | ID | ID customer/toko. | Maps to `0CUSTOMER` |
| `Material_code` | ID | Kode material. | Maps to `0MATERIAL` |
| `Mekanisme` | Text | Jenis promo (contoh: potongan harga). | - |
| `Program_Status` | Flag | Status program promo (aktif/tidak). | - |

---

## Ringkasan: 21 File → 7 Domain

```
┌─────────────────────────────────────────────────────────────────┐
│  REFERENCE (3 file), baca dulu                                  │
│  R1 Base UOM  │  R2 Key Figure  │  R3 Catatan                   │
├─────────────────────────────────────────────────────────────────┤
│  SALES (6 file), transaksi penjualan detail                     │
│  S1-S2 Oct  │  S3-S4 Nov  │  S5-S6 Dec                          │
├─────────────────────────────────────────────────────────────────┤
│  B2B (3 file), penjualan Key Account                            │
│  B1 Oct  │  B2 Nov  │  B3 Dec                                    │
├─────────────────────────────────────────────────────────────────┤
│  STOCK (4 file), posisi inventory                               │
│  ST1-ST3 Stock Tempo  │  ST4 Stock SAT-IDM                       │
├─────────────────────────────────────────────────────────────────┤
│  SERVICE LEVEL (1 file), KPI pemenuhan order                    │
│  SL1 Service Level Okt-Des                                      │
├─────────────────────────────────────────────────────────────────┤
│  LOGISTICS (2 file), operasional gudang                         │
│  L1 Picking  │  L2 Unloading                                     │
├─────────────────────────────────────────────────────────────────┤
│  SAT (2 file), audit lapangan                                   │
│  SAT1 OOS Okt-Des  │  SAT2 Promo Des saja                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Hubungan antar file (simplified)

```
         ┌──────────┐
         │ Reference│ ← kamus istilah
         └────┬─────┘
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐
│ Sales │ │  B2B  │ │ Stock │
└───┬───┘ └───┬───┘ └───┬───┘
    │         │         │
    └────┬────┴────┬────┘
         ▼         ▼
   ┌──────────┐ ┌───────┐
   │ Service  │ │  SAT  │
   │  Level   │ │ (OOS) │
   └──────────┘ └───────┘
         │
         ▼
   ┌──────────┐
   │Logistics │
   │(Picking) │
   └──────────┘
```

**Join keys antar file:**

| Key | Dipakai di file |
|-----|-----------------|
| `0CUSTOMER` / `cust_id` | Sales, B2B, Picking, SAT |
| `0MATERIAL` / `Material_code` | Sales, B2B, Stock, Service Level, SAT |
| `0SALES_OFF` / `sales_office` | Sales, B2B, Service Level, Picking, Unloading |
| `0CALMONTH` / `TGL_DCP` | Semua (kecuali Reference) |

---

## Quick lookup: "File X itu data apa?"

| Kalau lihat file ini... | Itu data... |
|-------------------------|-------------|
| `Sales *.txt` | Transaksi penjualan detail |
| `B2B *.txt` | Penjualan channel B2B/Key Account |
| `Stock *.txt` | Posisi stok di gudang |
| `Stock SAT-IDM *.xlsb` | Stok dari sistem SAT (TBC) |
| `Service Level *.txt` | KPI pemenuhan order |
| `Picking *.xlsx` | Proses ambil barang di gudang |
| `Unloading *.xlsx` | Proses bongkar barang di gudang |
| `SAT OOS *.xlsx` | Produk kosong di toko (lapangan) |
| `SAT Promo *.xlsx` | Promo di toko (lapangan) |
| `Base UOM *.xlsx` | Master satuan ukuran |
| `Custom Key Figure *.xlsx` | Kamus kode metrik SAP |
| `Catatan terkait Data *.xlsx` | Catatan/anomali dari Tempo |

---

---

## Referensi SAP Standard (InfoObject umum di dataset ini)

| InfoObject | Modul SAP | Definisi Standard |
|------------|-----------|-------------------|
| `0MATERIAL` | MM / LO | Material master. Identitas produk/barang. |
| `0CUSTOMER` | SD | Customer master. Identitas customer. |
| `0SALESORG` | SD | Sales organization. |
| `0SALES_OFF` | SD | Sales office / area penjualan. |
| `0SALES_GRP` | SD | Sales group. |
| `0SOLD_TO` | SD | Sold-to party. |
| `0CALMONTH` | BW | Calendar month (YYYYMM). |
| `0CALDAY` | BW | Calendar day (YYYYMMDD). |
| `0CALYEAR` | BW | Calendar year. |
| `0FISCPER` | FI / BW | Fiscal period. |
| `0BASE_UOM` | MM | Base unit of measure. |
| `0BILL_TYPE` | SD | Billing document type. |
| `0DOC_TYPE` | SD | Sales document type. |
| `0CUST_GRP3` | SD | Customer group level 3. |
| `0PLANT` (Plant) | MM | Plant / site / gudang. |
| `0STOR_LOC` | MM | Storage location. |
| `0STOCKCAT` | MM | Stock category. |
| `0STOCKTYPE` | MM | Stock type. |
| `0VENDOR` | MM | Vendor master. |
| `0PRODUCT` | LO | Product (supply chain view). |

Modul SAP yang relevan: **SD** (Sales & Distribution), **MM** (Material Management), **BW** (Business Warehouse).

---

*Companion dari `TEMPO_DATA_UNDERSTANDING.md`. Definisi variabel mengacu SAP standard kecuali kolom custom (Z*) atau dari sistem non-SAP (Logistics, SAT).*
