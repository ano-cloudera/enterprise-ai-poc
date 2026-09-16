from __future__ import annotations

from app.core.schemas import ChartSeries, ChartSpec
from app.semantic.intent import AnalyticalIntent


def build_chart(rows: list[dict], intent: AnalyticalIntent) -> ChartSpec:
    if not rows:
        return ChartSpec(type="none")
    dimension = intent.dimensions[0] if intent.dimensions else None
    dimension_key = "period" if dimension == "time" else dimension
    if intent.pattern == "kpi" and not dimension:
        return ChartSpec(type="none")
    if not dimension_key or dimension_key not in rows[0]:
        return ChartSpec(type="table", title="Query Result")
    x = [str(row.get(dimension_key, "")) for row in rows]
    if intent.comparison.type == "previous_period":
        return ChartSpec(
            type="bar",
            title="Current vs Previous Period",
            x=x,
            series=[
                ChartSeries(name="Current", data=[row.get("current_value") for row in rows]),
                ChartSeries(name="Previous", data=[row.get("previous_value") for row in rows]),
            ],
            x_label=dimension_key,
            y_label=intent.metric,
        )
    if intent.pattern == "trend":
        return ChartSpec(
            type="line",
            title="Trend",
            x=x,
            series=[ChartSeries(name=intent.metric, data=[row.get("value") for row in rows])],
        )
    if intent.pattern in {"breakdown", "top_bottom", "entity_comparison"}:
        return ChartSpec(type="bar", title="Breakdown", x=x, series=[ChartSeries(name=intent.metric, data=[row.get("value") for row in rows])])
    return ChartSpec(type="table", title="Query Result")
