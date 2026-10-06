# TEMPO Scan Frontend V2

Next.js Ask Data client adapted from the proven TEMPO frontend. Dashboard and Monitoring are removed. Chat/session history, TEMPO styling, table/KPI/Recharts components, and the SSE final-buffer fix are retained. Settings discovers its selectable models from Backend V2; the frontend has no hardcoded model list or credentials.

## Local run and tests

```bash
cd frontend
npm ci
cp .env.example .env.local   # BACKEND_API_URL=http://127.0.0.1:8001 for backend-tes local
./start.sh                   # or: npm run dev
npm test
npm run build
```

Start **backend-tes** on port **8001** before the UI (`backend-tes/./start.sh`). For governed **backend**, set `BACKEND_API_URL=http://127.0.0.1:8000` in `.env.local`.

The browser always calls same-origin `/api/*`. `next.config.mjs` proxies those calls server-side to `BACKEND_API_URL`, preserving the V1 workaround for CAI cross-origin gateway restrictions. `NEXT_PUBLIC_BACKEND_URL` is consumed by the CAI launcher and copied into server-only `BACKEND_API_URL`; no secret belongs in a `NEXT_PUBLIC_*` variable.

## Cloudera AI Application

Deploy as a separate CAI Application with the same Python runtime pattern as V1. Entrypoint:

```text
frontend/app_cai_frontend.py
```

Set `NEXT_PUBLIC_BACKEND_URL` to the deployed Backend V2 HTTPS Application URL. The launcher reuses system Node when present or downloads pinned portable Node 20.19.0, the minimum supported by the installed Vite toolchain. It runs `npm ci` when the lock changes, builds Next.js, starts the server as a monitored child process so CAI's interpreter kernel stays alive, uses `CDSW_APP_PORT`, and binds `127.0.0.1` behind the CAI proxy.

## Troubleshooting

- **`EADDRINUSE` on port 3000**: another dev server is already running — stop it or use `./start.sh` (no fixed port) so Next.js can bind 3001.
- **“Unable to discover configured AI models”**: backend not reachable at `BACKEND_API_URL` (common when v3 is on **8001** but the proxy still points at **8000**). Use `.env.local` or `./start.sh`, which loads it.
- No model is enabled: open the backend `/models` and configure at least one provider (local v3: pick **Gemini** in Settings).
- Engine exits immediately after a successful build: sync the latest launcher; CAI interpreter-cell execution requires the monitored child-process lifecycle rather than replacing the kernel with `os.execve`.
- API 404 through the frontend: verify `NEXT_PUBLIC_BACKEND_URL` points to the backend origin without a trailing `/api`; V2 backend endpoints are rooted at `/models`, `/chat`, and so on.
- Build should require no Google Fonts network access; V2 uses the system font stack.
- If SSE final data is missing, retain the current `src/lib/api.ts` buffer-drain behavior; the final chunk may arrive with `done=true`.
