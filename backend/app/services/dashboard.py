from __future__ import annotations

from datetime import datetime, timezone


def _ossie_metric_rows(metric: str, dimensions: list[str]) -> list[dict]:
    from app.ossie.service import OssieQueryRequest, get_tempo_ossie_service

    result = get_tempo_ossie_service().execute_query(
        OssieQueryRequest(
            metric=metric,
            dimensions=dimensions,
            start_calmonth=202410 if "calmonth" in dimensions else None,
            end_calmonth=202412 if "calmonth" in dimensions else None,
            limit=50,
        )
    )
    return result["rows"]


def _get_ossie_dashboard_overview() -> dict:
    sales_trend_rows = _ossie_metric_rows("gross_billing_value", ["calmonth"])
    fill_rate_rows = _ossie_metric_rows("company_fill_rate", ["calmonth"])
    office_rows = _ossie_metric_rows("sales_office_sell_in_value", ["sales_office"])
    material_rows = _ossie_metric_rows("material_sell_in_value", ["material"])
    sell_out_rows = _ossie_metric_rows("material_sell_out_value", [])

    sales_trend_rows.sort(key=lambda row: int(row["calmonth"]))
    fill_by_month = {
        int(row["calmonth"]): float(row.get("metric_value") or 0)
        for row in fill_rate_rows
    }
    current = float(sales_trend_rows[-1]["metric_value"] or 0) if sales_trend_rows else 0
    previous = float(sales_trend_rows[-2]["metric_value"] or 0) if len(sales_trend_rows) > 1 else 0
    growth = ((current - previous) / previous * 100) if previous else 0
    latest_month = int(sales_trend_rows[-1]["calmonth"]) if sales_trend_rows else 202412
    latest_fill_rate = fill_by_month.get(latest_month, 0) * 100
    top_material = str(material_rows[0]["material"]) if material_rows else "-"
    q4_sell_in = sum(float(row.get("metric_value") or 0) for row in sales_trend_rows)
    q4_sell_out = float(sell_out_rows[0].get("metric_value") or 0) if sell_out_rows else 0
    channel_total = q4_sell_in + q4_sell_out or 1

    return {
        "profile": "impala_ossie",
        "period": "Q4 2024",
        "kpis": [
            {
                "key": "gross_billing_value",
                "label": "Gross Sales (BILL_VAL)",
                "value": round(current, 2),
                "format": "currency_idr",
                "delta": round(growth, 1),
            },
            {
                "key": "growth",
                "label": "Monthly Growth",
                "value": round(growth, 1),
                "format": "percent",
                "delta": round(growth, 1),
            },
            {
                "key": "fill_rate",
                "label": "Company Fill Rate",
                "value": round(latest_fill_rate, 2),
                "format": "percent",
                "delta": None,
            },
            {
                "key": "top_material",
                "label": "Top Material",
                "value": top_material,
                "format": "text",
                "delta": None,
            },
        ],
        "sales_trend": [
            {
                "month": str(row["calmonth"]),
                "sales": round(float(row.get("metric_value") or 0) / 1_000_000, 2),
            }
            for row in sales_trend_rows
        ],
        "region_sales": [
            {
                "region": str(row["sales_office"]),
                "sales": round(float(row.get("metric_value") or 0) / 1_000_000, 2),
            }
            for row in office_rows[:10]
        ],
        "top_products": [
            {
                "product": str(row["material"]),
                "category": "Material",
                "sales": round(float(row.get("metric_value") or 0) / 1_000_000, 2),
            }
            for row in material_rows[:10]
        ],
        "channel_share": [
            {
                "channel": "Sell-In",
                "sales": round(q4_sell_in / 1_000_000, 2),
                "share": round(q4_sell_in / channel_total * 100, 1),
            },
            {
                "channel": "Sell-Out",
                "sales": round(q4_sell_out / 1_000_000, 2),
                "share": round(q4_sell_out / channel_total * 100, 1),
            },
        ],
        "labels": {
            "sales_trend": "Gross Sales Trend",
            "region_sales": "Sell-In by Sales Office",
            "top_products": "Top Materials",
            "channel_share": "Sell-In vs Sell-Out Context",
        },
        "scope_badges": [
            "Q4 2024",
            "Gross Sales = BILL_VAL",
            "Candidate metrics pending business confirmation",
        ],
        "ai_insight": {
            "headline": "Governed TEMPO Q4 2024 view",
            "summary": (
                "Metrics are sourced from audited Impala Gold semantic views. "
                "Sell-In and Sell-Out are shown separately."
            ),
            "actions": [
                "Review material-level drivers",
                "Investigate low Fill Rate materials",
                "Validate candidate KPIs with TEMPO business owners",
            ],
        },
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


def get_dashboard_overview() -> dict:
    return _get_ossie_dashboard_overview()
