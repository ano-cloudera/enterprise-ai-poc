from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import get_settings
from app.db.base import DataBackendError
from app.forecasting.tool import ForecastTool, resolve_forecast_intent
from app.llm.models import TrustedAnalysisPayload
from app.core.schemas import (
    ChangeDimensionAction,
    ChangeMetricAction,
    ExecutiveAnswer,
    ChartSpec,
    HighlightCardAction,
    RenderChartAction,
    RenderChartValue,
    ResetFilterAction,
    SetDateRangeAction,
    SetFilterAction,
    ShowTableAction,
    ShowTableValue,
    ui_action_adapter,
)
from app.guardrails.service import GuardrailService
from app.llm.factory import get_llm_provider
from app.llm.models import ModelTelemetry
from app.llm.payload import build_trusted_analysis_payload, deterministic_grounded_analysis, to_executive_answer
from app.llm.providers import LLMProviderError
from app.semantic.loader import allowed_columns, allowed_tables, load_semantic_project, semantic_prompt_context
from app.semantic.intent import AnalyticalIntent
from app.semantic.resolver import normalize_analytical_intent, resolve_analytical_intent
from app.services.query import QueryContext, query_service
from app.tools.chart_builder import build_chart
from app.tools.semantic_sql import generate_semantic_sql
from app.tools.ui_actions import validate_action_targets
from app.graph.state import GraphState


settings = get_settings()
logger = logging.getLogger(__name__)
guardrails = GuardrailService()


def input_guard(state: GraphState) -> GraphState:
    result = guardrails.validate_input(state["question"])
    if not result.allowed:
        return {**state, "guardrail_error": result.reason or "Input rejected", "status": "fallback", "fallback_used": True}
    return state


def _contains_alias(text: str, alias: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(alias.lower())}(?!\w)", text) is not None


def route_intent(state: GraphState) -> GraphState:
    q = state["question"].lower()
    if state.get("guardrail_error"):
        return {**state, "intent": "blocked"}
    forecast_terms = ("forecast", "proyeksi", "ramalan", "bulan depan", "next month")
    project = load_semantic_project()
    business_terms: set[str] = set()
    for dataset in project.datasets.values():
        business_terms.update((dataset.name.lower(), dataset.source.lower()))
        for key, metric in dataset.metrics.items():
            business_terms.update([key.lower(), metric.label.lower(), *(alias.lower() for alias in metric.aliases)])
        for key, dimension in dataset.dimensions.items():
            business_terms.update([key.lower(), dimension.label.lower(), *(alias.lower() for alias in dimension.aliases)])
    for values in project.resolution.entities.values():
        for item in values:
            business_terms.update([item.value.lower(), *(alias.lower() for alias in item.aliases)])
    reset_requested = any(_contains_alias(q, phrase) for phrase in project.resolution.reset_phrases)
    if any(term in q for term in forecast_terms):
        intent = "forecast"
    elif reset_requested or any(_contains_alias(q, term) for term in business_terms):
        intent = "analytical"
    else:
        intent = "conversational"
    return {**state, "intent": intent}


def resolve_semantics(state: GraphState) -> GraphState:
    """Resolve configured vocabulary while preserving explicit prior dashboard state."""
    project = load_semantic_project()
    q = state["question"].lower()
    prior = state.get("dashboard_state") or {}
    reset_requested = any(_contains_alias(q, phrase) for phrase in project.resolution.reset_phrases)
    candidate = resolve_analytical_intent(state["question"], {} if reset_requested else prior, project)
    dimension = next((item for item in candidate["dimensions"] if item != "time"), prior.get("dimension") or project.resolution.default_dimension)
    resolved = {
        "filters": candidate["filters"],
        "date_range": {"preset": candidate["time"]["period"], "start": None, "end": None},
        "metric": candidate["metric"],
        "dimension": dimension,
        "highlights": [] if reset_requested else [
            {"target": target, "value": value}
            for target, values in candidate["filters"].items()
            for value in values
        ],
        "ai_applied_context": [] if reset_requested else prior.get("ai_applied_context") or [],
        "revision": prior.get("revision", 0),
    }
    semantic_resolution = {
        "candidate_intent": candidate,
        "resolved_state": resolved,
        "reset_requested": reset_requested,
        "allowed_tables": sorted(allowed_tables(project)),
        "allowed_columns": sorted(allowed_columns(project)),
    }
    return {
        **state,
        "semantic_context": semantic_prompt_context(project),
        "semantic_resolution": semantic_resolution,
        "resolved_state": resolved,
        "reset_requested": reset_requested,
    }


def normalize_intent(state: GraphState) -> GraphState:
    project = load_semantic_project()
    candidate = (state.get("semantic_resolution") or {}).get("candidate_intent")
    intent = normalize_analytical_intent(candidate or {}, project)
    prior = state.get("resolved_state") or {}
    normalized = intent.model_dump()
    dimension = next((item for item in intent.dimensions if item != "time"), prior.get("dimension") or project.resolution.default_dimension)
    resolved = {
        **prior,
        "filters": intent.filters,
        "date_range": {"preset": intent.time.period, "start": intent.time.start, "end": intent.time.end},
        "metric": intent.metric,
        "dimension": dimension,
    }
    return {**state, "analytical_intent": normalized, "resolved_state": resolved}


async def generate_sql(state: GraphState) -> GraphState:
    intent = AnalyticalIntent.model_validate(state.get("analytical_intent"))
    dialect = "trino" if settings.data_backend == "trino" else "duckdb"
    sql = generate_semantic_sql(
        intent,
        load_semantic_project(),
        dialect,
        settings.trino_catalog if dialect == "trino" else "",
        settings.trino_schema if dialect == "trino" else "",
    )
    return {**state, "sql": sql, "sql_reason": "Deterministic SQL compiled from normalized semantic intent."}


async def repair_sql(state: GraphState) -> GraphState:
    intent = AnalyticalIntent.model_validate(state.get("analytical_intent"))
    dialect = "trino" if settings.data_backend == "trino" else "duckdb"
    sql = generate_semantic_sql(
        intent,
        load_semantic_project(),
        dialect,
        settings.trino_catalog if dialect == "trino" else "",
        settings.trino_schema if dialect == "trino" else "",
    )
    return {
        **state,
        "sql": sql,
        "sql_reason": "Deterministic SQL recompiled once from normalized semantic intent.",
        "repair_attempts": state.get("repair_attempts", 0) + 1,
    }


def validate_sql(state: GraphState) -> GraphState:
    result = query_service.validate(state.get("sql", ""), QueryContext(purpose="chat", project_id=settings.project_id))
    if result.valid:
        return {**state, "validated_sql": result.sql or "", "validation_status": "passed", "validation_error": ""}
    return {**state, "validation_status": "rejected", "validation_error": result.error or "Rejected"}


def execute_sql(state: GraphState) -> GraphState:
    try:
        result = query_service.execute_validated(
            state["validated_sql"],
            QueryContext(purpose="chat", project_id=settings.project_id, trace_id=state.get("trace_id", "")),
        )
        return {
            **state,
            "validated_sql": result.sql,
            "rows": result.rows,
            "data_telemetry": result.telemetry.model_dump() if result.telemetry else {},
            "status": "ok",
        }
    except DataBackendError as error:
        logger.warning("Validated data query failed safely trace_id=%s error_code=%s", state.get("trace_id"), error.code)
        return {
            **state,
            "rows": [],
            "status": "fallback",
            "fallback_used": True,
            "validation_error": "Query execution failed safely",
            "data_telemetry": error.telemetry.model_dump() if error.telemetry else {
                "data_backend": settings.data_backend,
                "success": False,
                "safe_error_code": error.code,
            },
        }
    except Exception:
        logger.exception("Validated query execution failed trace_id=%s", state.get("trace_id"))
        return {**state, "rows": [], "status": "fallback", "fallback_used": True, "validation_error": "Query execution failed safely"}


def result_checker(state: GraphState) -> GraphState:
    rows = state.get("rows", [])
    if not isinstance(rows, list):
        return {**state, "result_check_status": "INVALID_RESULT", "result_check_error": "Query result is not a row list"}
    if not rows:
        return {**state, "result_check_status": "EMPTY", "result_check_error": "Trusted query returned no rows"}
    if len(rows) > 5000:
        return {**state, "result_check_status": "INVALID_RESULT", "result_check_error": "Trusted query exceeded the result-size boundary"}
    intent = AnalyticalIntent.model_validate(state.get("analytical_intent"))
    if intent.comparison.type == "previous_period":
        expected = {"current_value", "previous_value", "absolute_change", "percentage_change"}
        if any(not expected.issubset(row) for row in rows):
            return {**state, "result_check_status": "INVALID_RESULT", "result_check_error": "Comparison result schema is invalid"}
        if all(row.get("current_value") is None and row.get("previous_value") is None for row in rows):
            return {**state, "result_check_status": "INVALID_RESULT", "result_check_error": "All comparison measures are null"}
        if all(row.get("previous_value") in (None, 0) for row in rows):
            return {**state, "result_check_status": "INSUFFICIENT_DATA", "result_check_error": "Comparison denominator is unavailable"}
    else:
        if any("value" not in row for row in rows):
            return {**state, "result_check_status": "INVALID_RESULT", "result_check_error": "Result schema does not match analytical intent"}
        if all(row.get("value") is None for row in rows):
            return {**state, "result_check_status": "INSUFFICIENT_DATA", "result_check_error": "All result measures are null"}
    return {**state, "result_check_status": "OK", "result_check_error": ""}


async def analyze_result(state: GraphState) -> GraphState:
    rows = state.get("rows", [])
    intent = AnalyticalIntent.model_validate(state.get("analytical_intent"))
    language = state.get("language", "auto")
    trace_id = state.get("trace_id", "")
    trusted_payload = build_trusted_analysis_payload(
        question=state.get("question", ""),
        language=language,
        intent=intent,
        rows=rows,
        project=load_semantic_project(),
    )
    try:
        result = await get_llm_provider().generate_structured(trusted_payload, language=language, trace_id=trace_id)
        analysis = result.analysis
        telemetry = result.telemetry
    except LLMProviderError as error:
        analysis = deterministic_grounded_analysis(trusted_payload, provider_unavailable=True)
        telemetry = ModelTelemetry(
            trace_id=trace_id,
            provider="qwen_openai_compatible",
            model=settings.qwen_model,
            latency_ms=error.latency_ms,
            retry_count=error.retry_count,
            success=False,
            fallback_used=True,
            http_status=error.http_status,
            structured_validation_success=False,
            error_code=error.code,
        )
    answer = to_executive_answer(analysis)
    return {
        **state,
        "answer": answer.model_dump(),
        "model_telemetry": telemetry.model_dump(),
        "fallback_used": state.get("fallback_used", False) or telemetry.fallback_used,
        "status": "ok",
    }


def visualization_planner(state: GraphState) -> GraphState:
    intent = AnalyticalIntent.model_validate(state.get("analytical_intent"))
    chart = build_chart(state.get("rows", []), intent)
    raw = chart.model_dump()
    raw["dimension"] = intent.dimensions[0] if intent.dimensions else None
    raw["metric"] = intent.metric
    raw["target"] = "chat"
    return {**state, "chart_spec": ChartSpec.model_validate(raw).model_dump()}


def ui_action_generator(state: GraphState) -> GraphState:
    """Generate only allowlisted declarative actions. No JS/code is ever emitted."""
    if state.get("reset_requested"):
        return {**state, "ui_actions": [ResetFilterAction(type="RESET_FILTER").model_dump(exclude_none=True)]}
    intent = AnalyticalIntent.model_validate(state.get("analytical_intent"))
    actions: list = []
    for target, values in intent.filters.items():
        actions.append(SetFilterAction(type="SET_FILTER", target=target, value=values))
    actions.append(SetDateRangeAction(type="SET_DATE_RANGE", value=intent.time.period))
    actions.append(ChangeMetricAction(type="CHANGE_METRIC", value=intent.metric))
    ui_dimension = next((item for item in intent.dimensions if item != "time"), None)
    if ui_dimension:
        actions.append(ChangeDimensionAction(type="CHANGE_DIMENSION", value=ui_dimension))
    for target, values in intent.filters.items():
        actions.append(HighlightCardAction(type="HIGHLIGHT_CARD", target=target, value=values))
    chart = state.get("chart_spec") or {}
    if chart.get("type") and chart.get("type") != "none":
        chart_dimension = "month" if intent.dimensions == ["time"] else (intent.dimensions[0] if intent.dimensions else (state.get("resolved_state") or {}).get("dimension"))
        if chart_dimension:
            actions.append(RenderChartAction(type="RENDER_CHART", target="chat", value=RenderChartValue(chart_type=chart["type"], dimension=chart_dimension, metric=intent.metric)))
    if state.get("rows"):
        columns = list(state["rows"][0].keys()) if state.get("rows") else []
        actions.append(ShowTableAction(type="SHOW_TABLE", target="chat", value=ShowTableValue(columns=columns)))
    return {**state, "ui_actions": [a.model_dump() for a in actions]}


def output_guard(state: GraphState) -> GraphState:
    if not state.get("answer"):
        return fallback(state)
    answer = ExecutiveAnswer.model_validate(state["answer"])
    result = guardrails.validate_output(answer)
    if not result.allowed:
        return fallback({**state, "guardrail_error": result.reason or "Output rejected"})
    # contract validation also prevents arbitrary UI action types from escaping
    actions = [ui_action_adapter.validate_python(a) for a in state.get("ui_actions", [])]
    validate_action_targets(actions, load_semantic_project())
    ChartSpec.model_validate(state.get("chart_spec") or {"type": "none"})
    return state


async def direct_chat(state: GraphState) -> GraphState:
    language = state.get("language", "auto")
    summary = "Silakan ajukan pertanyaan analitis berdasarkan data bisnis yang tersedia." if language == "id" else "Please ask an analytical question grounded in the available business data."
    answer = ExecutiveAnswer(summary=summary, drivers=[], recommended_actions=[])
    return {**state, "answer": answer.model_dump(), "chart_spec": {"type": "none", "title": "", "x": [], "series": []}, "ui_actions": [], "resolved_state": state.get("dashboard_state") or {}, "status": "ok"}


async def forecast(state: GraphState) -> GraphState:
    project = load_semantic_project()
    intent = resolve_forecast_intent(state["question"], state.get("dashboard_state") or {}, project)
    lookup = ForecastTool().get_sales_forecast(intent)
    resolved_state = state.get("dashboard_state") or {}
    if lookup.status == "FORECAST_NOT_AVAILABLE":
        requested = intent.forecast_period.strftime("%B %Y")
        summary = (
            f"Forecast untuk {requested} belum tersedia. Tidak ada angka forecast yang dibuat sebagai pengganti."
            if state.get("language") == "id"
            else f"The forecast for {requested} is not available. No substitute forecast was generated."
        )
        answer = ExecutiveAnswer(
            summary=summary,
            drivers=[],
            recommended_actions=["Tampilkan tren penjualan 3 bulan terakhir sebagai referensi historis."],
            caveats=["FORECAST_NOT_AVAILABLE"],
        )
        return {
            **state,
            "forecast_intent": intent.model_dump(mode="json"),
            "answer": answer.model_dump(),
            "rows": [],
            "chart_spec": {"type": "none", "title": "", "x": [], "series": []},
            "ui_actions": [],
            "resolved_state": resolved_state,
            "status": "fallback",
            "fallback_used": True,
        }

    rows = [row.model_dump(mode="json") for row in lookup.rows]
    first = lookup.rows[0]
    payload = TrustedAnalysisPayload(
        question=state["question"],
        language=state.get("language", "auto"),
        intent=intent.model_dump(mode="json"),
        business_context={
            "persisted_forecast": True,
            "model_name": first.model_name,
            "model_version": first.model_version,
            "training_cutoff_date": first.training_cutoff_date.isoformat(),
            "instruction": "Explain only; forecast values and bounds are immutable.",
        },
        query_result={"columns": list(rows[0]), "rows": rows},
    )
    try:
        model_result = await get_llm_provider().generate_structured(
            payload,
            language=state.get("language", "auto"),
            trace_id=state.get("trace_id", ""),
        )
        answer = to_executive_answer(model_result.analysis)
        model_telemetry = model_result.telemetry.model_dump()
    except LLMProviderError as error:
        answer = to_executive_answer(deterministic_grounded_analysis(payload, provider_unavailable=True))
        model_telemetry = {"success": False, "fallback_used": True, "error_code": error.code}
    chart = ChartSpec(
        type="line",
        title="Sales Forecast",
        x=[row.forecast_date.isoformat() for row in lookup.rows],
        series=[
            {"name": "Forecast", "data": [row.forecast_sales for row in lookup.rows]},
            {"name": "Lower bound", "data": [row.lower_bound for row in lookup.rows]},
            {"name": "Upper bound", "data": [row.upper_bound for row in lookup.rows]},
        ],
        x_label="Forecast period",
        y_label="Sales",
        dimension=intent.dimension_type,
        metric="forecast_sales",
        target="chat",
    )
    return {
        **state,
        "forecast_intent": intent.model_dump(mode="json"),
        "answer": answer.model_dump(),
        "rows": rows,
        "chart_spec": chart.model_dump(),
        "ui_actions": [],
        "model_telemetry": model_telemetry,
        "resolved_state": resolved_state,
        "status": "ok",
    }


def fallback(state: GraphState) -> GraphState:
    reason = state.get("guardrail_error") or state.get("validation_error") or state.get("result_check_error") or "The AI workflow could not return a validated answer."
    answer = ExecutiveAnswer(
        summary="Permintaan tidak dapat diproses menjadi jawaban analitis yang tervalidasi.",
        drivers=[],
        recommended_actions=["Gunakan pertanyaan bisnis berbasis data yang tersedia atau periksa konfigurasi data source."],
        caveats=[reason],
    )
    return {**state, "answer": answer.model_dump(), "chart_spec": {"type": "none", "title": "", "x": [], "series": []}, "ui_actions": [], "resolved_state": state.get("dashboard_state") or {}, "status": "fallback", "fallback_used": True}
