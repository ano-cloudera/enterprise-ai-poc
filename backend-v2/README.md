# TEMPO Scan Backend V2

FastAPI + controlled LangGraph Ask Data backend. V2 does not call Agent Studio. It resolves Apache Ossie metrics first, permits a controlled single-view SQL fallback, validates every query with SQLGlot, executes read-only Impala, and asks the selected provider for a grounded result analysis/chart contract.

## Local run and tests

```bash
python -m venv .venv
.venv/bin/pip install -r backend-v2/requirements.txt -r backend-v2/requirements-impala.txt
cp backend-v2/.env.example backend-v2/.env
PYTHONPATH=backend-v2 .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
PYTHONPATH=backend-v2 .venv/bin/pytest -q backend-v2/tests
```

`GET /health` is deliberately lightweight. `GET /health/ready` reports safe LLM, semantic, and Impala configuration readiness. `GET /models` reports configured availability. `GET /random-queries` supports `domain`, `difficulty`, and `limit`. `POST /chat` and `POST /chat/stream` accept `session_id`, `question`, `provider`, and the exact configured `model` returned by `/models`.

## Configuration

Copy `.env.example` and set the selected provider plus Impala values. Model IDs are never hardcoded in the frontend. Qwen needs a base URL, API token, and model; Gemini/OpenAI need an API key and model. Unconfigured providers remain unavailable without preventing startup. For the current Private Cloud deployment use the proven Impala GSSAPI + TLS values, query timeout, and a valid Kerberos ticket/service account. Never commit credentials.

Prompts live in `prompts/` and are resolved relative to the backend package, so CAI's working directory does not affect them. The copied `projects/tempo_scan_impala/ossie` files are the deployed 20-dataset/62-metric semantic authority.

## Cloudera AI Application

Create a dedicated CAI Application with the same Python 3.10 runtime pattern as V1. Entrypoint:

```text
backend-v2/app_cai_backend.py
```

Set provider and Impala variables from `.env.example`. The launcher creates `backend-v2/.venv-cai`, installs both requirement files, uses `CDSW_APP_PORT` (fallback `PORT`), and binds `127.0.0.1` because the CAI reverse proxy provides external HTTPS. Basic health URL is `/health`. Check CAI Application Logs for safe request IDs; credentials and raw exceptions are not returned to the browser.

## Troubleshooting

- Model disabled: inspect `/models`; set its model ID and required credential/base URL, then restart.
- `IMPALA_QUERY_FAILED`: verify Kerberos ticket/service principal, TLS, host/port, and whether HTTP transport/path is required in this environment.
- SSE appears frozen: confirm the CAI proxy preserves `text/event-stream`; V2 sends `X-Accel-Buffering: no`, no-transform caching, and 15-second heartbeat comments.
- Optional provider has no outbound network: leave it configured as unavailable or select Qwen; startup remains healthy.
