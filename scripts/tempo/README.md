# Tempo Data Pipeline (Scaffold)

Extract MTPL customer data: **raw → refine (parquet) → gold → Iceberg**.

Plan detail: `datasets/TEMPO_EXTRACTION_PLAN.md`

## Setup

```bash
cd /path/to/enterprise-ai-poc
python3 -m venv .venv-datasets
source .venv-datasets/bin/activate
pip install -r scripts/tempo/requirements.txt
```

## Prepare raw data

Copy customer files to:

- `datasets/raw/` (preferred)
- `datasets/data/` (fallback)

Expected layout:

```
datasets/raw/
├── Oct - Dec 2024 New/          (Sales *.txt)
├── B2B Oct - Dec 2024/          (B2B *.txt)
├── Stock Tempo Oct-Dec 2024/    (Stock *.txt)
├── Service Level Oct - Dec 2024.txt
├── SAT OOS Okt - Des 2024.xlsx
├── Base UOM.XLSX
├── Custom Key Figure Sales.xlsx
├── Catatan terkait Data.xlsx
└── _phase2/                     (fase 2, belum di-extract)
```

## Commands

```bash
# List domains + file readiness
python scripts/tempo/refine.py --list-domains

# Refine all phase-1 domains
python scripts/tempo/refine.py

# Refine one domain (POC)
python scripts/tempo/refine.py --domain sales

# Build gold fact/dim (basic scaffold)
python scripts/tempo/build_gold.py

# QA row counts + column profile
python scripts/tempo/qa_report.py

# CSV samples for human review (1000 rows)
python scripts/tempo/sample_csv.py
```

Run from repo root. Scripts add `scripts/tempo` to path automatically when invoked directly.

## Output

```
datasets/refine/parquet/     # sales.parquet, b2b.parquet, ...
datasets/refine/csv_sample/  # optional samples
datasets/refine/manifest/    # refine_manifest.json
datasets/gold/               # fact_*.parquet, dim_*.parquet
datasets/qa/                 # row_counts.json
```

## Config flags

Edit `scripts/tempo/config.yaml`:

- `transforms.scale_div100.enabled` — default `false` until Pak Gunawan confirms
- `transforms.scale_div100.columns` — populate after confirmation
- Domain file paths — `files` (new layout) vs `legacy_files` (flat MTPL)

## Next steps

1. POC: `refine.py --domain sales`
2. Validate row counts vs `datasets/README.md`
3. Full refine all domains
4. `build_gold.py` + `qa_report.py`
5. Load gold to Iceberg (Sprint 4)
