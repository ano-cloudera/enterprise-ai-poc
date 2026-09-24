from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import sqlglot
from sqlglot import exp
import yaml

from app.core.config import get_settings
from app.core.schemas import DashboardState
from app.semantic.loader import load_semantic_project
from app.semantic.models import PeriodRangeDefinition, SemanticProject
from app.services.query import QueryContext, QueryValidationError, query_service


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


def _load_dashboard_config() -> dict:
    settings = get_settings()
    with (settings.project_dir / "config.yaml").open("r", encoding="utf-8") as handle:
        project_config = yaml.safe_load(handle) or {}
    dashboard_file = project_config.get("dashboard_file")
    if not dashboard_file:
        raise RuntimeError("Project dashboard_file is not configured")
    with (settings.project_dir / dashboard_file).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _validated_filters(state: DashboardState, project: SemanticProject) -> dict[str, list[str]]:
    configured = {
        target: {item.value for item in values}
        for target, values in project.resolution.entities.items()
    }
    result: dict[str, list[str]] = {}
    for target, values in state.filters.items():
        if not values:
            continue
        if target not in configured:
            raise QueryValidationError(f"Unknown dashboard filter: {target}")
        if any(value not in configured[target] for value in values):
            raise QueryValidationError(f"Invalid governed value for filter: {target}")
        result[target] = values
    return result


def _period_for(mode: str | dict[str, str], state: DashboardState, project: SemanticProject) -> PeriodRangeDefinition:
    if isinstance(mode, dict):
        period = PeriodRangeDefinition.model_validate(mode)
    elif state.date_range.start and state.date_range.end:
        period = PeriodRangeDefinition(start=state.date_range.start, end=state.date_range.end)
    else:
        preset = state.date_range.preset or "current_month"
        if mode == "comparison":
            preset = project.resolution.comparison_periods.get(preset, "")
        period = project.resolution.period_ranges.get(preset)
        if period is None:
            raise QueryValidationError("Unknown dashboard date range")
    try:
        start = date.fromisoformat(period.start)
        end = date.fromisoformat(period.end)
    except ValueError as exc:
        raise QueryValidationError("Invalid dashboard date range") from exc
    if start >= end:
        raise QueryValidationError("Dashboard date range must have start before end")
    return period


def _build_query(spec: dict[str, Any], state: DashboardState, project: SemanticProject) -> str:
    try:
        root = sqlglot.parse_one(spec["sql"], read="hive")
    except Exception as exc:
        raise QueryValidationError("Invalid configured dashboard SQL") from exc
    filters = _validated_filters(state, project)
    period = _period_for(spec.get("period", "selected"), state, project)
    datasets_by_source = {dataset.source.lower(): dataset for dataset in project.datasets.values()}
    matched = []
    for table in root.find_all(exp.Table):
        qualified = ".".join(part for part in (table.catalog, table.db, table.name) if part).lower()
        dataset = datasets_by_source.get(qualified)
        if dataset is not None:
            matched.append(dataset)
    if not matched:
        raise QueryValidationError("Dashboard query does not use a governed dataset")

    conditions: list[exp.Expression] = []
    for dataset in matched:
        time_dimension = next(iter(dataset.time_dimensions.values()), None)
        if time_dimension:
            conditions.extend([
                exp.GTE(this=exp.column(time_dimension.column), expression=exp.cast(exp.Literal.string(period.start), "DATE")),
                exp.LT(this=exp.column(time_dimension.column), expression=exp.cast(exp.Literal.string(period.end), "DATE")),
            ])
        for target, values in filters.items():
            dimension = dataset.dimensions.get(target)
            if dimension:
                conditions.append(exp.column(dimension.column).isin(*[exp.Literal.string(value) for value in values]))
    for condition in conditions:
        root = root.where(condition)
    return root.sql(dialect="hive")


def _rows(spec: dict[str, Any], purpose: str, state: DashboardState, project: SemanticProject) -> list[dict]:
    settings = get_settings()
    sql = _build_query(spec, state, project)
    return query_service.execute_validated(sql, QueryContext(purpose=purpose, project_id=settings.project_id)).rows


def get_dashboard_overview(state: DashboardState | None = None) -> dict:
    if get_settings().semantic_execution_mode == "ossie":
        return _get_ossie_dashboard_overview()
    state = state or DashboardState()
    project = load_semantic_project()
    config = _load_dashboard_config()
    queries = config["queries"]
    current = (_rows(queries["current_sales"], "dashboard.current_sales", state, project) or [{}])[0].get("sales") or 0
    previous = (_rows(queries["previous_sales"], "dashboard.previous_sales", state, project) or [{}])[0].get("sales") or 0
    growth = ((current - previous) / previous * 100) if previous else 0
    trend = _rows(queries["sales_trend"], "dashboard.sales_trend", state, project)
    regions = _rows(queries["region_sales"], "dashboard.region_sales", state, project)
    products = _rows(queries["top_products"], "dashboard.top_products", state, project)
    channels = _rows(queries["channel_share"], "dashboard.channel_share", state, project)
    inventory_rows = _rows(queries["inventory_health"], "dashboard.inventory_health", state, project)
    inventory = (inventory_rows or [{}])[0].get("healthy_pct") or 0
    total_channel = sum(float(row["sales"] or 0) for row in channels) or 1
    return {
        "period": state.date_range.preset.replace("_", " ").title() if state.date_range.preset else f"{state.date_range.start} – {state.date_range.end}",
        "kpis": [
            {"key": "net_sales", "label": "Net Sales", "value": round(current, 1), "format": "currency_billion", "delta": round(growth, 1)},
            {"key": "growth", "label": "Growth vs Comparison", "value": round(growth, 1), "format": "percent", "delta": round(growth, 1)},
            {"key": "inventory", "label": "Inventory Health", "value": round(inventory, 1), "format": "percent", "delta": None},
            {"key": "top_region", "label": "Top Region", "value": regions[0]["region"] if regions else "-", "format": "text", "delta": None},
        ],
        "sales_trend": trend,
        "region_sales": regions,
        "top_products": products,
        "channel_share": [{**row, "share": round(float(row["sales"] or 0) / total_channel * 100, 1)} for row in channels],
        "ai_insight": config.get("insight", {"headline": "", "summary": "", "actions": []}),
    }
