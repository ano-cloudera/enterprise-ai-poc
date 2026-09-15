from __future__ import annotations

from typing import Any

from app.core.schemas import ExecutiveAnswer
from app.llm.models import AnalysisDriver, StructuredAnalysis, TrustedAnalysisPayload
from app.semantic.intent import AnalyticalIntent
from app.semantic.models import SemanticProject


def build_trusted_analysis_payload(
    *, question: str, language: str, intent: AnalyticalIntent, rows: list[dict[str, Any]], project: SemanticProject
) -> TrustedAnalysisPayload:
    dataset = next(dataset for dataset in project.datasets.values() if intent.metric in dataset.metrics)
    metric = dataset.metrics[intent.metric]
    relevant_dimensions = {name for name in [*intent.dimensions, *intent.filters] if name != "time"}
    dimensions = {
        name: {
            "label": dataset.dimensions[name].label,
            "description": dataset.dimensions[name].description,
        }
        for name in relevant_dimensions
        if name in dataset.dimensions
    }
    compact_intent = {
        "pattern": intent.pattern,
        "metric": intent.metric,
        "dimensions": intent.dimensions,
        "filters": intent.filters,
        "time": intent.time.model_dump(),
        "comparison": intent.comparison.model_dump(),
    }
    return TrustedAnalysisPayload(
        question=question,
        language=language,
        intent=compact_intent,
        business_context={
            "metric_definition": {
                "name": intent.metric,
                "label": metric.label,
                "aggregation": metric.aggregation,
                "description": metric.description,
            },
            "dimension_definitions": dimensions,
        },
        query_result={"columns": list(rows[0]) if rows else [], "rows": rows[:200]},
    )


def deterministic_grounded_analysis(payload: TrustedAnalysisPayload, *, provider_unavailable: bool = False) -> StructuredAnalysis:
    rows = payload.query_result.get("rows") or []
    first = rows[0] if rows else {}
    if "forecast_sales" in first:
        forecast = first.get("forecast_sales")
        lower = first.get("lower_bound")
        upper = first.get("upper_bound")
        period = first.get("forecast_date")
        dimension = first.get("dimension_value", "ALL")
        summary = (
            f"Forecast {dimension} untuk {period} adalah {forecast}, dengan rentang {lower} hingga {upper}."
            if payload.language == "id"
            else f"The {dimension} forecast for {period} is {forecast}, with a range from {lower} to {upper}."
        )
        caveats = ["AI analysis was unavailable; this explanation was generated directly from persisted forecast results."] if provider_unavailable else []
        return StructuredAnalysis(
            summary=summary,
            drivers=[AnalysisDriver(title="Persisted forecast", description="The values were retrieved from the governed offline forecast table.", evidence=f"forecast_sales={forecast}; lower_bound={lower}; upper_bound={upper}")],
            recommended_actions=[],
            caveats=caveats,
        )
    measure_fields = {"value", "current_value", "previous_value", "absolute_change", "percentage_change"}
    dimension_key = next((key for key in first if key not in measure_fields), None)
    dimension_value = str(first.get(dimension_key, "result")) if dimension_key else "result"
    drivers: list[AnalysisDriver] = []
    if {"current_value", "previous_value", "percentage_change"}.issubset(first):
        current = first.get("current_value")
        previous = first.get("previous_value")
        percentage = first.get("percentage_change")
        change = first.get("absolute_change")
        if payload.language == "id":
            summary = f"Nilai {dimension_value} berubah {percentage}% dibanding periode sebelumnya, dari {previous} menjadi {current}."
        else:
            summary = f"{dimension_value} changed by {percentage}% versus the previous period, from {previous} to {current}."
        drivers.append(AnalysisDriver(
            title="Trusted comparison",
            description=f"{dimension_value} is the leading returned comparison row.",
            evidence=f"current_value={current}; previous_value={previous}; absolute_change={change}; percentage_change={percentage}",
        ))
    elif "value" in first:
        value = first.get("value")
        summary = f"{dimension_value} memiliki nilai {value}." if payload.language == "id" else f"{dimension_value} has a value of {value}."
        drivers.append(AnalysisDriver(title="Trusted result", description=f"The executed query returned {dimension_value}.", evidence=f"value={value}"))
    else:
        summary = "Tidak ada hasil tepercaya yang dapat diringkas." if payload.language == "id" else "No trusted result was available to summarize."
    caveats = ["AI analysis was unavailable; this summary was generated directly from trusted query results."] if provider_unavailable else []
    return StructuredAnalysis(summary=summary, drivers=drivers, recommended_actions=[], caveats=caveats)


def to_executive_answer(analysis: StructuredAnalysis) -> ExecutiveAnswer:
    return ExecutiveAnswer(
        summary=analysis.summary,
        drivers=[f"{driver.title}: {driver.description} Evidence: {driver.evidence}" for driver in analysis.drivers],
        recommended_actions=analysis.recommended_actions,
        caveats=analysis.caveats,
    )
