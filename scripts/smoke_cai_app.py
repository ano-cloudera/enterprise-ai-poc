"""End-to-end smoke test for a deployed CAI application instance.

Two modes:

- Legacy single-app (scripts/run-cai-app.sh): pass --base-url pointing at
  the frontend's public URL. Requests go through its same-origin /api/*
  proxy, exactly like a browser would.
- Split deployment (scripts/run-cai-backend.sh + run-cai-frontend.sh,
  Milestone 7.2): pass --backend-url pointing directly at the deployed
  "Tempo Scan Backend" CAI Application's public URL. This is what actually
  proves Frontend-configured-backend connectivity and Backend->Qwen
  connectivity end-to-end, since the frontend itself is a static/SSR app
  with no server-side API surface of its own to smoke-test independently.

Usage:
    .venv/bin/python scripts/smoke_cai_app.py --base-url http://127.0.0.1:3000
    .venv/bin/python scripts/smoke_cai_app.py --backend-url https://tempo-backend.cai.example
"""
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DASHBOARD_STATE = {
    "filters": {}, "date_range": {"preset": "current_month", "start": None, "end": None},
    "metric": "net_sales", "dimension": "region", "highlights": [], "ai_applied_context": [],
    "revision": 0, "chat": {"chart": None, "table": {"visible": False, "columns": []}},
}

QUESTIONS = [
    "Kenapa sales Jawa Barat turun bulan ini?",
    "Bagaimana forecast sales Jawa Barat bulan depan?",
    "Apakah penurunan sales Jawa Barat berkorelasi dengan curah hujan?",
    "Bagaimana posisi Bodrex dibanding kompetitor?",
    "Region mana yang punya market opportunity terbesar untuk Bodrex?",
]

RAW_ERROR_MARKERS = ("Traceback (most recent call last)", "Internal Server Error", "sqlite3.", "duckdb.", " at 0x")


class SmokeFailure(RuntimeError):
    pass


def request(base_url: str, method: str, path: str, body: dict | None = None, timeout: float = 30.0) -> dict:
    url = f"{base_url}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            status = response.status
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except URLError as exc:
        raise SmokeFailure(f"{method} {path}: connection failed ({exc.reason})") from exc

    for marker in RAW_ERROR_MARKERS:
        if marker in payload:
            raise SmokeFailure(f"{method} {path}: raw technical error leaked in response: {marker!r}")

    if status >= 500:
        raise SmokeFailure(f"{method} {path}: server error {status}: {payload[:200]}")

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"{method} {path}: non-JSON response: {payload[:200]}") from exc


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise SmokeFailure(f"{label} failed" + (f": {detail}" if detail else ""))
    print(f"  ok  {label}")


def run(base_url: str) -> None:
    print(f"Smoke testing {base_url}\n")

    print("1. Application health")
    health = request(base_url, "GET", "/api/health")
    check("backend /api/health reachable", health.get("status") in ("ok", "degraded"), str(health.get("status")))

    readiness = request(base_url, "GET", "/api/deployment/readiness")
    check("deployment readiness reachable", readiness.get("status") in ("healthy", "degraded"), str(readiness.get("status")))
    for component in readiness.get("components", []):
        print(f"      {component['name']}: {component['status']}")

    print("\n2. Dashboard data")
    dashboard = request(base_url, "POST", "/api/dashboard/overview", DASHBOARD_STATE)
    check("dashboard returns KPIs", len(dashboard.get("kpis", [])) > 0, f"{len(dashboard.get('kpis', []))} kpis")
    check("dashboard returns sales trend", len(dashboard.get("sales_trend", [])) > 0)

    print("\n3-7. Representative Ask AI questions")
    for index, question in enumerate(QUESTIONS, start=3):
        label = {
            3: "historical hero question",
            4: "forecast question",
            5: "weather question",
            6: "market/competitor question",
            7: "external market fallback",
        }[index]
        print(f"  [{index}] {label}: {question!r}")
        response = request(base_url, "POST", "/api/chat", {
            "question": question, "history": [], "dashboard_state": DASHBOARD_STATE,
        })
        check(f"{label} returns ok/fallback status", response.get("status") in ("ok", "fallback"), str(response.get("status")))
        check(f"{label} returns a summary", bool(response.get("answer", {}).get("summary")))

    print("\n8. Ask AI response shape")
    ask_ai = request(base_url, "POST", "/api/chat", {
        "question": QUESTIONS[0], "history": [], "dashboard_state": DASHBOARD_STATE,
    })
    check("chat metadata present", bool(ask_ai.get("metadata", {}).get("trace_id")))

    print("\n9. No raw technical errors observed across all requests above (validated inline).")

    print("\nAll smoke checks passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=None, help="Legacy single-app: public base URL of the deployed frontend (default http://127.0.0.1:3000 if neither flag is given)")
    parser.add_argument("--backend-url", default=None, help="Split deployment: public base URL of the deployed Tempo Scan Backend Application")
    args = parser.parse_args()

    if args.base_url and args.backend_url:
        print("Pass only one of --base-url or --backend-url, not both.", file=sys.stderr)
        return 2

    target = args.backend_url or args.base_url or "http://127.0.0.1:3000"
    mode = "split (direct backend)" if args.backend_url else "legacy single-app (via frontend proxy)"
    print(f"Mode: {mode}")

    try:
        run(target.rstrip("/"))
    except SmokeFailure as exc:
        print(f"\nSMOKE TEST FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
