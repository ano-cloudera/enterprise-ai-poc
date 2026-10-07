# backend-test — TEMPO exploratory local

Agent-driven **read-only SQL** over **DuckDB `silver.*` sample** (9 domains). Same `/chat` and `/chat/stream` contract as backend for **frontend**.

## Quick start

```bash
cd backend-test
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # GEMINI_API_KEY or GOOGLE_API_KEY (Google AI Studio, google-genai SDK)
python scripts/seed_local_silver.py
chmod +x start.sh && ./start.sh   # http://127.0.0.1:8001
```

## Frontend (local)

```bash
cd frontend
BACKEND_API_URL=http://127.0.0.1:8001 npm run dev
```

Responses use `strategy=exploratory_local`. Treat numbers as **sample data**, not Impala/gold official KPIs.

## Real on-prem sample (optional)

Export parquet per table into `local_data/parquet/{table_name}.parquet`, then re-run:

```bash
python scripts/seed_local_silver.py
```

Parquet overrides synthetic seed for matching table names (see `scripts/seed_local_silver.py`).

## Architecture

- **No Ossie resolver** — LLM tool loop: `list_tables` → `describe_table` → `run_sql` → `AnalysisOutput`
- **SQL guard** — SELECT-only, `silver` schema, no `SELECT *`, row cap
- **Knowledge** — `knowledge/tempo_domains.md` (gold concepts as text)

## vs backend

| v2 | v3 |
|----|-----|
| Impala gold + governed metrics | DuckDB silver sample |
| Deterministic resolver | Autonomous SQL agent |
| Production CAI demo | Local BOD / literacy testing |
