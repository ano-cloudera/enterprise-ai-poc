# Tempo: Plan Ekstraksi Data (raw → refine → Iceberg)

**Status:** Approved (brainstorm Sep 2026)
**Tujuan:** Extract & rapikan data MTPL sambil menunggu jawaban klarifikasi Tempo, supaya siap load ke **Iceberg**.

**Prinsip:**
- Kerjakan yang sudah pasti dulu, jangan block di jawaban Tempo
- Format utama refine: **Parquet** (bukan CSV)
- CSV hanya sample untuk review human
- Transform pending (÷ 100, join key) di-parameterize via config

**Referensi:** `TEMPO_DATAMART_PLAN.md`, `TEMPO_FILE_MAPPING.md`, `TEMPO_KLARIFIKASI_JAWABAN.md`

---

## 1. Folder Structure

```
datasets/
├── raw/                              # source as-is dari customer (TXT, XLSX)
│
├── refine/                           # hasil cleaning + normalize
│   ├── parquet/                      # ← format utama (wajib)
│   │   ├── sales.parquet
│   │   ├── b2b.parquet
│   │   ├── stock.parquet
│   │   ├── service_level.parquet
│   │   ├── oos.parquet
│   │   ├── dim_uom.parquet
│   │   └── dim_key_figure.parquet
│   ├── csv_sample/                   # ← opsional, max 1000 rows/table
│   │   └── sales_sample.csv
│   └── manifest/                     # metadata extract
│       ├── refine_manifest.json      # file list, row count, timestamp
│       └── column_map.json           # mapping SAP → snake_case
│
├── gold/                             # datamart fact + dim (star schema)
│   ├── fact_sales.parquet
│   ├── fact_b2b_sales.parquet
│   ├── fact_stock.parquet
│   ├── fact_service_level.parquet
│   ├── fact_oos.parquet
│   ├── dim_customer.parquet
│   ├── dim_material.parquet
│   ├── dim_sales_org.parquet
│   ├── dim_plant.parquet
│   ├── dim_time.parquet
│   ├── dim_uom.parquet
│   └── dim_key_figure.parquet
│
├── qa/                               # QA reports
│   ├── row_counts.json
│   ├── grain_check.json
│   └── sellin_sellout_gap.csv
│
└── format_slide/                     # slide deck (existing)
```

**Catatan:** Semua folder di atas **gitignored** kecuali dokumen markdown yang di-whitelist.

---

## 2. Pipeline Flow

```
raw/*.txt,xlsx
        │
        ▼  Step 1: extract + clean + union per domain
refine/parquet/*.parquet
        │
        ▼  Step 2: build fact/dim (star schema)
gold/*.parquet
        │
        ▼  Step 3: register catalog
Iceberg: tempo_poc.fact_sales, dim_material, ...
        │
        ▼  Step 4: query via Trino/Impala
Semantic layer + Ask AI
```

---

## 3. Format Decision

| Layer | Format | Alasan |
|-------|--------|--------|
| **raw/** | As-is (TXT, XLSX) | Tidak diubah, backup source |
| **refine/parquet/** | **Parquet (snappy)** | Typed, compact, native Iceberg |
| **refine/csv_sample/** | CSV (1000 rows max) | Review human / share ke Tempo |
| **gold/** | Parquet | Input langsung ke Iceberg |
| **Iceberg** | Parquet + metadata | Target production query |

**Tidak pakai CSV full** — Sales saja bisa 500MB+ per domain.

---

## 4. Source Files → Refine Output

### Fase 1 — Extract sekarang (17 file → 7 parquet)

| ID | Source file (raw/MTPL/) | Format | Refine output | Priority |
|----|-------------------------|--------|---------------|----------|
| S1 | `raw/Oct - Dec 2024 New/Sales 1-15 Oct 2024.txt` | TXT | `refine/parquet/sales.parquet` | P0 |
| S2 | `Sales 16-31 Oct 2024.txt` | TXT | ↑ union ke sales | P0 |
| S3 | `Sales 1-15 Nov 2024.txt` | TXT | ↑ union | P0 |
| S4 | `Sales 16-30 Nov 2024.txt` | TXT | ↑ union | P0 |
| S5 | `Sales 1-15 Dec 2024.txt` | TXT | ↑ union | P0 |
| S6 | `Sales 16-31 Dec 2024.txt` | TXT | ↑ union | P0 |
| B1 | `B2B 10.2024.txt` | TXT | `refine/parquet/b2b.parquet` | P0 |
| B2 | `B2B 11.2024.txt` | TXT | ↑ union | P0 |
| B3 | `B2B 12.2024.txt` | TXT | ↑ union | P0 |
| ST1 | `Stock 10.2024.txt` | TXT | `refine/parquet/stock.parquet` | P1 |
| ST2 | `Stock 11.2024.txt` | TXT | ↑ union | P1 |
| ST3 | `Stock 12.2024.txt` | TXT | ↑ union | P1 |
| SL1 | `Service Level Oct - Dec 2024.txt` | TXT | `refine/parquet/service_level.parquet` | P1 |
| SAT1 | `SAT OOS Okt - Des 2024.xlsx` | XLSX | `refine/parquet/oos.parquet` | P2 |
| R1 | `Base UOM.XLSX` | XLSX | `refine/parquet/dim_uom.parquet` | P1 |
| R2 | `Custom Key Figure Sales.xlsx` | XLSX | `refine/parquet/dim_key_figure.parquet` | P1 |
| R3 | `Catatan terkait Data.xlsx` | XLSX | `refine/manifest/transform_rules.json` | P1 |

### Fase 2 — Tunda (4 file)

| ID | Source file | Alasan defer |
|----|-------------|--------------|
| ST4 | `Stock SAT-IDM Monthly Okt-Des 24.xlsb` | Format `.xlsb`, belum di-inspect |
| L1 | `Picking Okt - Des 24.xlsx` | Out of scope PoC fase 1 |
| L2 | `Unloading Okt - Des 24.xlsx` | Out of scope PoC fase 1 |
| SAT2 | `SAT Promo Des 24.xlsx` | Cuma Desember |

---

## 5. Gold Layer → Iceberg Tables

### Fact tables (5)

| Gold file | Iceberg table | Source refine | Grain | Partition |
|-----------|---------------|---------------|-------|-----------|
| `fact_sales.parquet` | `tempo_poc.fact_sales` | sales | customer + material + cabang + bulan | `calmonth` |
| `fact_b2b_sales.parquet` | `tempo_poc.fact_b2b_sales` | b2b | customer + material + cabang + bulan | `calmonth` |
| `fact_stock.parquet` | `tempo_poc.fact_stock` | stock | material + plant + stor_loc + bulan | `calmonth` |
| `fact_service_level.parquet` | `tempo_poc.fact_service_level` | service_level | material + cabang + cust_group + bulan | `calmonth` |
| `fact_oos.parquet` | `tempo_poc.fact_oos` | oos | customer + material + tanggal | `calmonth` |

**Channel flag (sudah dikonfirmasi Tempo):**

| Fact | channel | Revenue |
|------|---------|---------|
| fact_sales | `sell_in` | `bill_val` |
| fact_b2b_sales | `sell_out` | `bill_val` |

### Dimension tables (6)

| Gold file | Iceberg table | Source |
|-----------|---------------|--------|
| `dim_time.parquet` | `tempo_poc.dim_time` | Generate 202410-202412 |
| `dim_customer.parquet` | `tempo_poc.dim_customer` | Distinct Sales + B2B + OOS |
| `dim_material.parquet` | `tempo_poc.dim_material` | Distinct Sales + B2B + Stock + SL |
| `dim_sales_org.parquet` | `tempo_poc.dim_sales_org` | Distinct dari Sales |
| `dim_plant.parquet` | `tempo_poc.dim_plant` | Distinct dari Stock |
| `dim_uom.parquet` | `tempo_poc.dim_uom` | R1 Base UOM |
| `dim_key_figure.parquet` | `tempo_poc.dim_key_figure` | R2 Custom Key Figure |

**Total Iceberg tables fase 1:** 12 (5 fact + 6 dim + 1 ref opsional)

Schema detail: lihat `TEMPO_DATAMART_PLAN.md` Section 2.

---

## 6. Transform Rules (refine stage)

### Semua SAP TXT

| Rule | Status |
|------|--------|
| Skip 3 baris header SAP | ✅ Pasti |
| Tab-delimited, UTF-8 | ✅ Pasti |
| Rename kolom → snake_case (`0MATERIAL` → `material_id`) | ✅ Pasti |
| Strip whitespace | ✅ Pasti |
| Add `_source_file`, `_loaded_at` | ✅ Pasti |
| Cast numeric & date columns | ✅ Pasti |

### Sales (6 file → 1 parquet)

| Rule | Status |
|------|--------|
| Union S1-S6 | ✅ Pasti |
| Nov: keep `calday` (nullable di file lain) | ✅ Pasti |
| Dec 16-31: `DO Amount` → `do_amt`, `Net Sales` → `net_sales` | ✅ Pasti |
| Key figure ÷ 100 (ZIOKF*, ZCOST, DIS_*) | ⏸ Pending Pak Gunawan |

### B2B (3 file → 1 parquet)

| Rule | Status |
|------|--------|
| Union B1-B3 | ✅ Pasti |

### Stock (3 file → 1 parquet)

| Rule | Status |
|------|--------|
| Union ST1-ST3 | ✅ Pasti |
| Masked columns (`...TOTSTCK`) rename best-effort | ⚠️ Partial |

### Service Level (1 file)

| Rule | Status |
|------|--------|
| `Lead = 4` → `lead_time` | ✅ Pasti |
| ZIOKF0034-0069: keep as columns | ✅ Pasti |

### SAT OOS (XLSX)

| Rule | Status |
|------|--------|
| `TGL_DCP` Excel serial → date | ✅ Pasti |
| `Cust Id` → `customer_id`, `Material_code` → `material_id` | ✅ Pasti |
| Aggregate harian → bulanan | ⏸ Optional (view terpisah) |

---

## 7. Implementation Timeline

### Sprint 1: raw → refine (3-4 hari) — mulai sekarang

| # | Task | Output |
|---|------|--------|
| 1.1 | Setup folder `datasets/raw/`, `refine/`, `gold/`, `qa/` | Struktur folder |
| 1.2 | Copy/link MTPL ke `datasets/raw/MTPL/` | Source ready |
| 1.3 | Script `scripts/tempo/refine.py`: SAP TXT parser | Parser module |
| 1.4 | Extract P0: Sales + B2B → `refine/parquet/` | sales.parquet, b2b.parquet |
| 1.5 | Extract P1: Stock + Service Level + Reference | 3 parquet + 2 dim |
| 1.6 | Extract P2: SAT OOS | oos.parquet |
| 1.7 | Generate csv_sample (1000 rows/table) | `refine/csv_sample/` |
| 1.8 | QA: row count, kolom, null % | `qa/row_counts.json` |

**DoD Sprint 1:** 7 file parquet di `refine/parquet/` + manifest + QA report.

### Sprint 2: refine → gold (2-3 hari)

| # | Task | Output |
|---|------|--------|
| 2.1 | Build dim tables (dedup) | 6 dim parquet di `gold/` |
| 2.2 | Build fact tables (map ke schema plan) | 5 fact parquet di `gold/` |
| 2.3 | Grain validation (no duplicate keys) | `qa/grain_check.json` |
| 2.4 | Sell In vs Sell Out sanity check | `qa/sellin_sellout_gap.csv` |
| 2.5 | Load gold ke DuckDB local (optional) | `runtime/tempo.duckdb` |

**DoD Sprint 2:** 12 file parquet di `gold/` + grain check pass.

### Sprint 3: Apply jawaban Tempo (1 hari)

| # | Task | Trigger |
|---|------|---------|
| 3.1 | Apply ÷ 100 ke kolom yang dikonfirmasi | Jawaban Pak Gunawan (#9) |
| 3.2 | Update dim_key_figure dengan definisi Z* | Jawaban Tim Tempo (#4) |
| 3.3 | Adjust join views | Jawaban relasi (#1) |
| 3.4 | Re-run refine + gold + QA | Post-transform |

### Sprint 4: gold → Iceberg (2-3 hari)

| # | Task | Output |
|---|------|--------|
| 4.1 | DDL Iceberg tables (partition `calmonth`) | SQL scripts |
| 4.2 | Load gold parquet → Iceberg catalog | 12 tables live |
| 4.3 | Connect backend `data_backend=trino` | Live query |
| 4.4 | Update semantic layer YAML | `projects/tempo_scan/semantic/` |

---

## 8. Script Structure

```
scripts/tempo/
├── config.yaml                 # paths, file manifest, transform flags
├── refine.py                   # raw → refine/parquet
├── build_gold.py               # refine → gold
├── qa_report.py                # generate qa/*.json
├── sample_csv.py               # parquet → csv_sample (1000 rows)
├── transforms/
│   ├── sap_txt.py              # parser SAP export (skip 3 header)
│   ├── column_map.py           # rename Dec cols, snake_case
│   ├── scale_div100.py         # ÷ 100 (config flag)
│   └── excel_dates.py          # TGL_DCP serial → date
└── README.md
```

**Config (`config.yaml`):**

```yaml
paths:
  raw: datasets/raw/MTPL
  refine: datasets/refine/parquet
  csv_sample: datasets/refine/csv_sample
  gold: datasets/gold
  qa: datasets/qa

transforms:
  scale_div100:
    enabled: false              # flip true setelah Pak Gunawan
    columns: []
  oos_aggregate_monthly:
    enabled: false

csv_sample:
  max_rows: 1000
```

---

## 9. QA Checklist

| Check | Expected |
|-------|----------|
| Row count Sales (6 file union) | ~3-4M |
| Row count B2B (3 file union) | ~4-5M |
| Row count Stock (3 file union) | ~500K |
| Duplicate grain keys per fact | 0 |
| Null rate material_id, calmonth | < 1% |
| Dec rename applied | `do_amt` exists, no `DO Amount` |
| Sell In vs Sell Out overlap | Materials comparable, no double-count |
| Parquet readable via DuckDB | `SELECT COUNT(*) FROM 'refine/parquet/sales.parquet'` |

---

## 10. Yang Ditunda (tunggu jawaban Tempo)

| Item | PIC | Poin klarifikasi |
|------|-----|------------------|
| Apply ÷ 100 | Pak Gunawan | #9 |
| Definisi Z* lengkap | Tim Tempo | #4 |
| Join cross-domain | Tim Tempo | #1 |
| Stock SAT-IDM, Logistics, SAT Promo | Internal | Fase 2 |

---

## 11. Langkah Immediate

1. Buat folder `datasets/raw/`, `refine/`, `gold/`, `qa/`
2. Pastikan source files ada di `datasets/raw/` (flat layout)
3. Buat `scripts/tempo/config.yaml` dengan file manifest 17 file fase 1
4. POC: extract **1 file Sales** → `refine/parquet/sales_partial.parquet`
5. Validasi: skip header, kolom, row count
6. Expand ke semua P0 (Sales union + B2B union)

---

## 12. Count Summary

| Kategori | Jumlah |
|----------|--------|
| Source files total | 21 |
| Extract fase 1 | 17 |
| Defer fase 2 | 4 |
| Refine parquet files | 7 |
| Gold / Iceberg tables | 12 |
| CSV sample files | 7 (opsional) |

---

*Update plan ini setelah jawaban follow-up Tempo masuk.*
