from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT / "README.md",
    ROOT / "backend/app/main.py",
    ROOT / "backend/app/graph/workflow.py",
    ROOT / "backend/app/tools/sql_validator.py",
    ROOT / "frontend/src/views/DashboardPage.tsx",
    ROOT / "frontend/src/views/AskAIPage.tsx",
    ROOT / "projects/tempo_scan/semantic/manifest.yaml",
    ROOT / "projects/tempo_scan/fixtures/commercial_sales_daily.csv",
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    print("Missing required files:", *missing, sep="\n- ")
    sys.exit(1)

sales = ROOT / "projects/tempo_scan/fixtures/commercial_sales_daily.csv"
monthly = defaultdict(float)
with sales.open(encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        if row["region_name"] == "Jawa Barat":
            monthly[row["sales_date"][:7]] += float(row["sales_amount"])

feb = monthly["2024-02"]
mar = monthly["2024-03"]
growth = (mar / feb - 1) * 100
if not (-19 <= growth <= -14):
    print(f"Hero story drifted: expected Jawa Barat decline around -17%, got {growth:.2f}%")
    sys.exit(1)

print(json.dumps({
    "status": "ok",
    "required_files": len(required),
    "jawa_barat_feb_sales_million_idr": round(feb, 2),
    "jawa_barat_mar_sales_million_idr": round(mar, 2),
    "jawa_barat_growth_pct": round(growth, 2),
}, indent=2))
