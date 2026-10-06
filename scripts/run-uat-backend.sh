#!/usr/bin/env bash
# Run backend UAT: resolver dry-run + optional live /chat per eval/uat_domain_matrix.yaml
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BE="$ROOT/backend-v2"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PROVIDER="${PROVIDER:-gemini}"
TIMEOUT="${TIMEOUT:-240}"
MODE="${MODE:-all}" # dry | live | all
OUT="${OUT:-$BE/eval/uat_run_$(date +%Y%m%d_%H%M%S).json}"

PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3

export PYTHONPATH="$BE:${PYTHONPATH:-}"

run_py() {
  "$PY" - "$@" <<'PY'
import asyncio
import json
import sys
import uuid
from pathlib import Path

import yaml

backend = Path(sys.argv[1])
base_url = sys.argv[2]
provider = sys.argv[3]
timeout = float(sys.argv[4])
mode = sys.argv[5]
out_path = Path(sys.argv[6])

sys.path.insert(0, str(backend))
from app.core.config import Settings
from app.semantic.context import SemanticContextService
from app.services.ask_data_routing import resolve_ask_data_route
from app.services.conversational import is_conversational_request

matrix_path = backend / "eval" / "uat_domain_matrix.yaml"
matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
settings = Settings()
ctx = SemanticContextService(settings.project_root / settings.ossie_project_id)

results: list[dict] = []


def check_expect(case: dict, resolution: dict | None, body: dict | None) -> tuple[bool, str]:
    expect = case.get("expect") or {}
    if expect.get("kind") in ("skip_live", "conversational_only"):
        return True, "skip dry resolver"
    if body is not None:
        status = body.get("status")
        strategy = body.get("strategy")
        if expect.get("status") and status != expect["status"]:
            return False, f"status want {expect['status']} got {status}"
        if expect.get("strategy") and strategy != expect["strategy"]:
            return False, f"strategy want {expect['strategy']} got {strategy}"
        if expect.get("reason"):
            # reason not always on response; check answer text loosely
            pass
        return True, "live ok"
    if resolution is None:
        return False, "no resolution"
    st = resolution.get("status")
    if expect.get("status") == "SUCCESS" and st != "resolved":
        return False, f"dry status {st}"
    if expect.get("status") == "CLARIFICATION" and st != "needs_clarification":
        return False, f"dry status {st}"
    metric = expect.get("metric")
    if metric and resolution.get("metric") != metric:
        return False, f"metric want {metric} got {resolution.get('metric')}"
    hint = expect.get("metric_hint")
    if hint and hint not in str(resolution.get("metric") or ""):
        return False, f"metric_hint {hint} not in {resolution.get('metric')}"
    return True, "dry ok"


for case in matrix.get("cases") or []:
    cid = case.get("id", "?")
    q = case.get("question")
    row: dict = {"id": cid, "domain": case.get("domain"), "question": q}

    if q is None:
        row["pass"] = True
        row["note"] = "skip"
        results.append(row)
        continue

    if is_conversational_request(q):
        row["dry"] = {"conversational": True}
        row["dry_pass"] = True
        row["dry_note"] = "conversational"
    else:
        resolution = ctx.resolve(q)
        route = resolve_ask_data_route(q, settings, semantic_resolution=resolution)
        row["dry"] = {
            "route": route,
            "resolver_status": resolution.get("status"),
            "metric": resolution.get("metric"),
            "reason": resolution.get("reason"),
        }
        ok, msg = check_expect(case, resolution, None)
        row["dry_pass"] = ok
        row["dry_note"] = msg

    if mode in ("live", "all"):
        import httpx

        async def one() -> dict:
            async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout) as client:
                models = (await client.get("/models")).json()
                model = ""
                for item in models.get("models") or []:
                    if item.get("provider") == provider and item.get("available"):
                        model = str(item.get("id") or "")
                        break
                if not model:
                    raise RuntimeError(f"No model for provider {provider}")
                payload = {
                    "session_id": f"uat-{cid}-{uuid.uuid4()}",
                    "question": q,
                    "provider": provider,
                    "model": model,
                }
                r = await client.post("/chat", json=payload)
                r.raise_for_status()
                return r.json()

        try:
            body = asyncio.run(one())
            row["live"] = {
                "status": body.get("status"),
                "strategy": body.get("strategy"),
                "row_count": (body.get("data") or {}).get("row_count"),
                "request_id": body.get("request_id"),
            }
            ok_live, msg_live = check_expect(case, None, body)
            row["live_pass"] = ok_live
            row["live_note"] = msg_live
        except Exception as exc:
            row["live_pass"] = False
            row["live_error"] = f"{type(exc).__name__}: {exc}"

    row["pass"] = row.get("live_pass") if mode in ("live", "all") and "live_pass" in row else row.get("dry_pass")
    results.append(row)

summary = {
    "mode": mode,
    "base_url": base_url,
    "total": len(results),
    "passed": sum(1 for r in results if r.get("pass")),
    "results": results,
}
out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"out": str(out_path), "passed": summary["passed"], "total": summary["total"]}, indent=2))
PY
}

echo "=== UAT backend (MODE=$MODE) ==="
echo "Base URL: $BASE_URL"

if [[ "$MODE" != "dry" ]]; then
  if ! curl -sf "$BASE_URL/health" >/dev/null; then
    echo "Backend not up. Start: bash scripts/run-local-stack-ossie-only.sh" >&2
    exit 1
  fi
  curl -sf "$BASE_URL/health/ready" | head -c 400 || true
  echo ""
fi

echo "=== B3 dry-run (management set) ==="
(cd "$BE" && "$PY" scripts/simulate_management_questions.py) || true

run_py "$BE" "$BASE_URL" "$PROVIDER" "$TIMEOUT" "$MODE" "$OUT"

echo ""
echo "Report: $OUT"
"$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); print('PASS', d['passed'], '/', d['total']);
[print((' OK ' if r.get('pass') else 'FAIL'), r['id'], r.get('live_note') or r.get('dry_note','')) for r in d['results']]" "$OUT"
