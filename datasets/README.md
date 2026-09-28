# MTPL Dataset Catalog

> **CONFIDENTIAL** - Data asli customer. Jangan commit, share, atau expose ke environment publik.
> Folder `datasets/` sudah di-exclude di `.gitignore`.

## Ringkasan

Dataset ini berasal dari sistem **SAP BW/ERP** (format export "Dynamic List Display") milik customer **MTPL**, covering periode **Oktober–Desember 2024**. Domain bisnis: **FMCG / distribusi retail** di Indonesia, covering sales, B2B, inventory, logistics (picking/unloading), service level, dan field audit (SAT).

**Total volume:** ~21 file | ~2.9 GB (TXT ~2.65 GB + Excel ~0.25 GB)

---

## Struktur Folder

```
datasets/MTPL/
├── _reference/                         ← metadata & lookup tables
│   ├── Base UOM.XLSX
│   ├── Custom Key Figure Sales.xlsx
│   └── Catatan terkait Data.xlsx
│
├── sales/                              ← transaksi penjualan (SAP BW)
│   └── Oct - Dec 2024 New/            (6 file, split per bulan & periode)
│
├── b2b/                                ← penjualan B2B per customer
│   └── B2B Oct - Dec 2024/          (3 file, per bulan)
│
├── stock/                              ← inventory / stok gudang
│   ├── Stock Tempo Oct-Dec 2024/      (3 file TXT, per bulan)
│   └── Stock SAT-IDM Monthly Okt-Des 24.xlsb
│
├── logistics/                          ← operasional gudang
│   ├── Picking Okt - Des 24.xlsx
│   └── Unloading Okt - Des 24.xlsx
│
├── sat/                                ← Sales Audit Team (field data)
│   ├── SAT OOS Okt - Des 2024.xlsx    (Out of Stock)
│   └── SAT Promo Des 24.xlsx
│
└── Service Level Oct - Dec 2024.txt   ← KPI service level (DO/PO/NSP)
```

---

## Detail per Dataset

### 1. Sales (`Oct - Dec 2024 New/`)

Transaksi billing/penjualan detail dari SAP BW. Split per bulan dan periode tanggal (1–15 vs 16–akhir bulan) karena volume besar.

| File | Periode | ~Rows | Cols | Size |
|------|---------|-------|------|------|
| Sales 1-15 Oct 2024.txt | Oct 1–15 | 358K | 60 | 191 MB |
| Sales 16-31 Oct 2024.txt | Oct 16–31 | 900K | 60 | 491 MB |
| Sales 1-15 Nov 2024.txt | Nov 1–15 | 390K | 61 | 207 MB |
| Sales 16-30 Nov 2024.txt | Nov 16–30 | 881K | 61 | 478 MB |
| Sales 1-15 Dec 2024.txt | Dec 1–15 | 337K | 60 | 178 MB |
| Sales 16-31 Dec 2024.txt | Dec 16–31 | 831K | 60 | 461 MB |

**Dimensi kunci:** Customer, Material, Sales Org/Office/Group, Bill Type, Route, Sub-hub, Fiscal Period
**Metrik kunci:** BILL_QTY, BILL_VAL, CN_AMT/QTY (credit note), DO_AMT/QTY (delivery order), berbagai discount (DIS_*), ZCOST (COGS), custom key figures (ZIOKF0028–0033)

**Format:** Tab-delimited SAP export. Skip 3 baris header sebelum row kolom.

**Catatan dari customer:**
- Nilai key figure terkait value perlu **× 100**
- Nov 2024 punya kolom tambahan `0CALDAY` (daily granularity)
- Dec 16–31: `DO Amount` dan `Net Sales` menggantikan `DO_AMT` dan `VV802`

---

### 2. B2B Sales (`B2B Oct - Dec 2024/`)

Penjualan channel B2B (Key Account / modern trade).

| File | ~Rows | Cols | Size |
|------|-------|------|------|
| B2B 10.2024.txt | 1.64M | 12 | 148 MB |
| B2B 11.2024.txt | 1.62M | 12 | 146 MB |
| B2B 12.2024.txt | 1.62M | 12 | 146 MB |

**Kolom:** BASE_UOM, CALMONTH, Currency, CUSTOMER, MATERIAL, SALES_OFF, BRANCH, E_STORE (masked), KA Group, Kode PLU, BILL_QTY, BILL_VAL

---

### 3. Service Level (`Service Level Oct - Dec 2024.txt`)

KPI fulfillment: Delivery Order vs Purchase Order, lead time, NSP (Net Sales Price?).

| ~Rows | Cols | Size |
|-------|------|------|
| 224K | 49 | 136 MB |

**Dimensi:** Material, Sales Org/Office, Customer Group, Calendar Month/Year
**Metrik:** DO_AMT/QTY, PO_AMT/QTY, NSP, Lead time, ZIOKF0034–0069 (custom KPIs)

---

### 4. Stock (`Stock Tempo Oct-Dec 2024/` + `.xlsb`)

Inventory snapshot per material, plant, storage location.

| File | ~Rows | Cols | Size |
|------|-------|------|------|
| Stock 10.2024.txt | 178K | 17 | 23 MB |
| Stock 11.2024.txt | 177K | 17 | 23 MB |
| Stock 12.2024.txt | 184K | 17 | 24 MB |
| Stock SAT-IDM Monthly Okt-Des 24.xlsb | - | - | 504 KB |

**Kolom:** MATERIAL, Plant, PRODUCT, STOCKCAT, STOCKTYPE, STOR_LOC, Vendor, CALMONTH, UPD_DATE, BASE_UOM, RECORDTP, + stock qty/value columns (partially masked)

---

### 5. Logistics

| File | ~Rows | Deskripsi |
|------|-------|-----------|
| Picking Okt - Des 24.xlsx | 350K | Proses picking: sales office, ship-to, delivery no, qty (mat/cart/tot), durasi (iMenitPick), cycle, status |
| Unloading Okt - Des 24.xlsx | 1.7K | Proses unloading: document, durasi (iMenit), qty DN/mat/tot |

---

### 6. SAT - Sales Audit Team (`SAT *.xlsx`)

Data lapangan dari audit kunjungan toko.

| File | ~Rows | Deskripsi |
|------|-------|-----------|
| SAT OOS Okt - Des 2024.xlsx | 901K | Out of Stock: tanggal DCP, customer, material/PLU, stok akhir |
| SAT Promo Des 24.xlsx | 71K | Promo di lapangan: mekanisme promo, program status (Des 2024 only) |

---

### 7. Reference Tables (`_reference/`)

| File | Isi |
|------|-----|
| Base UOM.XLSX | Master unit of measure SAP (~300+ UOM: KG, DUS, KAR, BOT, dll.) |
| Custom Key Figure Sales.xlsx | Mapping kode SAP custom → deskripsi bisnis |
| Catatan terkait Data.xlsx | Notes dari customer tentang transformasi & anomali data |

**Custom Key Figures:**

| Kode | Deskripsi |
|------|-----------|
| ZIOKF0028 | Cash Discount Sales |
| ZOKF0029 | Cash Discount Return |
| ZOKF0030 | Disc. Principal F1 |
| ZOKF0031 | Disc. F5 Add Hoc |
| ZOKF0032 | Disc. Invoice Volume |
| ZOKF0033 | Disc. CN Volume |
| ZIOCH0042 | Customer Number (Sales View) |
| ZCOST | COGS Value |

---

## Format Teknis

### SAP TXT Export
- **Delimiter:** Tab (`\t`)
- **Header rows to skip:** 3 (baris 1–3 adalah metadata SAP "Dynamic List Display")
- **Header row:** Baris 4 (index 3)
- Beberapa kolom di-mask dengan prefix `...` (redacted by SAP export)

### Excel
- `.xlsx` = standard OpenXML, readable dengan openpyxl/pandas
- `.xlsb` = binary Excel (Stock SAT-IDM), butuh pyxlsb engine

---

## Relasi Antar Dataset (Entity Map)

```
Customer ──┬── Sales (billing)
           ├── B2B Sales
           ├── Service Level (DO/PO fulfillment)
           └── SAT (OOS, Promo audit)

Material ──┬── Sales / B2B
           ├── Stock
           ├── Service Level
           └── SAT (OOS, Promo)

Sales Office ──┬── Sales
               ├── B2B
               ├── Service Level
               ├── Picking
               └── Unloading

Plant / Storage Loc ── Stock
```

---

## Known Issues & Data Quality Notes

1. **Sales key figures × 100** - nilai discount/custom figures perlu dibagi 100 saat interpretasi
2. **Kolom inconsistent antar periode** - Nov punya `0CALDAY`, Dec 16–31 rename beberapa kolom
3. **Masked columns** - beberapa field SAP di-redact (`...E_STORE`, `...T_GROUP`, dll.)
4. **Mixed naming** - `0MATERIAL` vs `Material`, `DO_AMT` vs `DO Amount`, `VV802` vs `Net Sales`
5. **Large file sizes** - B2B & Sales 16–31 per file 150–490 MB; perlu chunked processing
6. **SAT Promo** - hanya Desember 2024 (tidak full Q4)

---

## Rekomendasi untuk PoC

1. **Prioritas ingest:** Sales + B2B + Stock (core analytics triangle)
2. **Enrichment:** Join via `0MATERIAL`, `0CUSTOMER`, `0SALES_OFF`, `0CALMONTH`
3. **Reference lookup:** Load Base UOM & Custom Key Figure sebagai dimension tables
4. **Processing:** Gunakan DuckDB/Spark dengan tab-delimiter parser, skip 3 header rows
5. **Security:** Keep datasets local only; never push to remote git
