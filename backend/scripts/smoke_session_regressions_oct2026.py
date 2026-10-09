#!/usr/bin/env python3
"""Smoke multi-turn chat scenarios that regressed in Oct 2026 UAT (live backend + Impala)."""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from typing import Any

import httpx

BASE = "http://127.0.0.1:8000"
PROVIDER = "gemini"
TIMEOUT = 300.0


def _metric(body: dict[str, Any]) -> str:
    data = body.get("data") or {}
    return str(data.get("governed_metric") or body.get("governed_metric") or "")


def _rows(body: dict[str, Any]) -> int:
    return int((body.get("data") or {}).get("row_count") or 0)


async def ask(client: httpx.AsyncClient, sid: str, question: str, model: str) -> dict[str, Any]:
    r = await client.post(
        "/chat",
        json={"session_id": sid, "question": question, "provider": PROVIDER, "model": model},
    )
    r.raise_for_status()
    return r.json()


async def main() -> int:
    failures: list[str] = []
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        models = (await client.get("/models")).json()
        model = ""
        for item in models.get("models") or []:
            if item.get("provider") == PROVIDER and item.get("available"):
                model = str(item.get("id") or "")
                break
        if not model:
            print("No gemini model", file=sys.stderr)
            return 1

        scenarios: list[tuple[str, list[tuple[str, dict[str, Any]]]]] = [
            (
                "stock_sat → Palembang → top 3 produk paling laku",
                [
                    (
                        "Top 10 DC Partner Alfamart berdasarkan stok Q4 2024",
                        {"status": "SUCCESS", "metric_contains": "sat_dc", "min_rows": 5},
                    ),
                    (
                        "bisa bantu analisa gak untuk daerah palembang?",
                        {"status": "SUCCESS", "min_rows": 0},
                    ),
                    (
                        "untuk DC palembang, apakah bisa bantu buat tampilkan top 3 produk apa yang paling laku",
                        {
                            "status": "SUCCESS",
                            "metric_contains": "b2b_branch_material_sell_out",
                            "min_rows": 1,
                            "forbid_status": ["NO_DATA"],
                        },
                    ),
                ],
            ),
            (
                "top 10 DC terbaik Q4 (sell-out B2B, bukan stok)",
                [
                    (
                        "Tampilkan top 10 DC terbaik Alfamart berdasarkan penjualan Q4 2024",
                        {
                            "status": "SUCCESS",
                            "metric_contains": "b2b_branch_sell_out",
                            "min_rows": 5,
                        },
                    ),
                ],
            ),
        ]

        for label, turns in scenarios:
            sid = f"smoke-{uuid.uuid4().hex[:10]}"
            print(f"\n=== {label} (session={sid}) ===")
            for q, expect in turns:
                body = await ask(client, sid, q, model)
                status = body.get("status")
                metric = _metric(body)
                rows = _rows(body)
                print(f"Q: {q[:70]}...")
                print(f"   status={status} strategy={body.get('strategy')} metric={metric} rows={rows}")
                forbid = expect.get("forbid_status") or []
                if status in forbid:
                    failures.append(f"{label}: forbidden status {status} for Q={q!r}")
                want = expect.get("status")
                if want and status != want:
                    failures.append(f"{label}: want status {want} got {status} — Q={q!r}")
                mc = expect.get("metric_contains")
                if mc and mc not in metric:
                    failures.append(f"{label}: metric missing {mc!r} got {metric!r}")
                min_rows = expect.get("min_rows")
                if min_rows is not None and status == "SUCCESS" and rows < int(min_rows):
                    failures.append(f"{label}: rows {rows} < {min_rows} — Q={q!r}")

        print("\n--- summary ---")
        if failures:
            for f in failures:
                print("FAIL:", f)
            return 1
        print("All smoke scenarios passed.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
