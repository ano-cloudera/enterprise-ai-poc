# Quickstart

1. Copy `.env.example` to `.env`.
2. Keep `LLM_MODE=mock` for the first local run.
3. Run `bash scripts/setup-local.sh`.
4. Run `make dev`.
5. Open `http://127.0.0.1:3000`.
6. Ask `Kenapa sales Jawa Barat turun bulan ini?`.
7. Inspect the collapsed technical trace in Ask AI.
8. Switch to `LLM_MODE=remote` only after local flow is stable.
9. Keep `DATA_BACKEND=duckdb` until the Milestone 5 Trino/CDW adapter and read-only credentials are available.
