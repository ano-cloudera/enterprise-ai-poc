# Cloudera AI Deployment Direction

## Model application

Do not change the proven Qwen application unless required. Current assumptions from the handoff:
- Qwen3.8-27B-AWQ
- vLLM 0.29.0
- NVIDIA L40S
- internal vLLM `127.0.0.1:9000`
- public FastAPI proxy via `CDSW_READONLY_PORT`
- thinking disabled by default

## Business application

Recommended final shape:

1. Build the Next.js frontend: `npm run build`.
2. Package the generated `.next` application with its production Node.js runtime, or add a separately reviewed static-export deployment mode.
3. Route `/api/*` to FastAPI from the single CAI application entrypoint or an approved reverse proxy.
4. Set `QWEN_BASE_URL`, `QWEN_MODEL`, and `QWEN_API_TOKEN` through CAI environment/secrets.
5. In Milestone 5, set Trino credentials through CAI environment/secrets, never source code.
6. Bind the business app to `CDSW_READONLY_PORT` or the customer-approved app port pattern.

The current bundle runs frontend/backend separately for easier local vibe coding. Single-port CAI packaging is intentionally the last mile, not mixed into foundation development.
