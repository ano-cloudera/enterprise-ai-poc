from __future__ import annotations

import logging
import re
from typing import Any
from datetime import date, timedelta

from app.core.config import get_settings
from app.db.base import DataBackendError
from app.forecasting.tool import ForecastTool, resolve_forecast_intent
from app.external_signals.weather.service import load_weather_governance, resolve_weather_intent
from app.external_signals.weather.tool import WeatherAnalysisTool
from app.market_intelligence.service import MarketIntelligenceTool, load_market_governance, resolve_market_intent
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


# Common Indonesian function words/particles that rarely appear in English
# sentences - used only to break the tie when the request's language is
# "auto" (the default the frontend always sends; it never sends "id"
# explicitly). Deliberately not exhaustive or linguistically rigorous: this
# only needs to pick between two languages for short business questions,
# not classify arbitrary text.
_INDONESIAN_MARKER_WORDS = (
    "apakah", "bagaimana", "berapa", "kenapa", "mengapa", "yang", "dengan", "dari",
    "untuk", "adalah", "tidak", "belum", "sudah", "akan", "bisa", "saat", "ini",
    "bulan", "tahun", "minggu", "hari", "turun", "naik", "produk", "wilayah",
    "termasuk", "semua", "data", "penjualan", "pelanggan", "jumlah",
)


def _resolve_language(question: str, language: str) -> str:
    """Returns "id" or "en" for deterministic (non-LLM) template branches.
    `language` is the request's declared setting - "auto" (the frontend's
    permanent default; explicit "id"/"en" always wins outright) means the
    caller never picked a language, so infer it from the question text
    instead of silently defaulting to English."""
    if language in ("id", "en"):
        return language
    text = question.lower()
    hits = sum(1 for word in _INDONESIAN_MARKER_WORDS if _contains_alias(text, word))
    return "id" if hits >= 1 else "en"


async def route_intent(state: GraphState) -> GraphState:
    q = state["question"].lower()
    if state.get("guardrail_error"):
        return {**state, "intent": "blocked"}
    forecast_terms = ("forecast", "proyeksi", "ramalan", "bulan depan", "next month")
    weather_terms = (
        "weather", "cuaca", "curah hujan", "hujan", "rainy day", "hari hujan",
        "temperatur", "temperature", "suhu", "humidity", "kelembapan",
    )
    market_terms = (
        "market", "kompetitor", "competitor", "pesaing", "opportunity", "price positioning",
        "distribution gap", "competitive pressure", "tekanan kompetitif",
    )
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
    if any(term in q for term in weather_terms):
        intent = "weather"
    elif any(term in q for term in market_terms):
        intent = "market"
    elif any(term in q for term in forecast_terms):
        intent = "forecast"
    elif reset_requested or any(_contains_alias(q, term) for term in business_terms):
        intent = "analytical"
    elif not _is_greeting(q) and any(_contains_alias(q, term) for term in project.resolution.measure_request_terms):
        # No configured metric/dimension/entity name matched, but the
        # question is clearly asking for a business quantity ("berapa",
        # "margin", "jumlah customer") - route to analytical so
        # resolve_semantics's metric_unavailable check can give a specific,
        # honest "that data isn't governed here, but X/Y/Z is" answer,
        # rather than falling through to the generic conversational
        # "that's outside what I can help with" reply.
        intent = "analytical"
    elif _is_greeting(q):
        intent = "conversational"
    elif _has_active_analytical_context(state):
        # No business keyword matched, but the session already has an
        # analytical thread going (prior turns, or dashboard filters
        # already resolved from an earlier question) - this could be a
        # genuine follow-up ("what else drove it?") or an unrelated aside
        # ("can you speak Indonesian?", "who are you?"). Keyword lists
        # can't reliably tell those apart, so ask the model to judge intent
        # from meaning rather than guessing "analytical" by default.
        intent = await _classify_ambiguous_intent(state)
    else:
        intent = "conversational"
    return {**state, "intent": intent}


async def _classify_ambiguous_intent(state: GraphState) -> str:
    try:
        result = await get_llm_provider().classify_intent(
            state["question"],
            conversation_history=state.get("history", []),
            trace_id=state.get("trace_id", ""),
        )
        return result.classification.intent
    except LLMProviderError:
        # LLM unavailable - fall back to the previous conservative
        # heuristic (treat as analytical whenever context exists) rather
        # than silently dropping every ambiguous follow-up.
        return "analytical"


def _has_active_analytical_context(state: GraphState) -> bool:
    """True once this session has evidence of a prior analytical turn: an
    actual conversation history, or a dashboard filter explicitly applied
    (region/product/channel, etc). Deliberately ignores `dashboard_state`
    fields like `dimension`/`metric` that always carry a non-empty default
    value even on a brand-new session - those would otherwise make every
    first message look like a follow-up."""
    if state.get("history"):
        return True
    filters = (state.get("dashboard_state") or {}).get("filters") or {}
    return any(filters.get(key) for key in filters)


_GOVERNANCE_PROBE_TERMS = (
    "tidak governed", "not governed", "yang tidak governed", "ungoverned",
    "bypass", "di luar governed", "outside governed", "semua data", "all data",
    "raw data", "data mentah", "tanpa restriction", "without restriction",
    "akses penuh", "full access", "abaikan governance", "ignore governance",
)


def resolve_semantics(state: GraphState) -> GraphState:
    """Resolve configured vocabulary while preserving explicit prior dashboard state."""
    project = load_semantic_project()
    q = state["question"].lower()
    prior = state.get("dashboard_state") or {}
    reset_requested = any(_contains_alias(q, phrase) for phrase in project.resolution.reset_phrases)
    # The question still only ever resolves to governed metrics/dimensions/
    # columns below (SQL generation and validate_sql both enforce the same
    # allowlist regardless), so this can't actually widen data access - but
    # if the user explicitly asked to bypass governance, silently answering
    # the governed question as if nothing unusual was asked reads as if the
    # request was ignored rather than declined. Flag it so analyze_result
    # can say plainly that access stays governed either way.
    governance_probe_detected = any(_contains_alias(q, term) for term in _GOVERNANCE_PROBE_TERMS)
    candidate = resolve_analytical_intent(state["question"], {} if reset_requested else prior, project)
    if candidate.get("metric_unavailable"):
        return {**state, "intent": "metric_unavailable"}
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
        "governance_probe_detected": governance_probe_detected,
    }


def metric_unavailable(state: GraphState) -> GraphState:
    """The question asked for a specific count/amount that has no matching
    configured metric (see resolve_semantics/resolve_analytical_intent's
    measure_request_terms check) - answer honestly instead of silently
    substituting a different metric (e.g. answering "how many customers"
    with Net Sales)."""
    language = _resolve_language(state["question"], state.get("language", "auto"))
    summary = (
        "Data yang diminta belum tersedia di dataset governed saat ini. Metric yang tersedia mencakup Net Sales, Sales Volume, dan Transactions."
        if language == "id"
        else "The requested data isn't available in the governed dataset yet. Available metrics are Net Sales, Sales Volume, and Transactions."
    )
    # caveats intentionally empty: summary already explains this in plain
    # language, and the frontend renders caveats verbatim to the user - an
    # internal status code like "METRIC_NOT_CONFIGURED" here would leak as
    # raw text on screen instead of the sentence above.
    answer = ExecutiveAnswer(summary=summary, drivers=[], recommended_actions=[], caveats=[])
    return {
        **state, "answer": answer.model_dump(), "rows": [],
        "chart_spec": {"type": "none", "title": "", "x": [], "series": []}, "ui_actions": [],
        "resolved_state": state.get("dashboard_state") or {}, "status": "fallback", "fallback_used": True,
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
        conversation_history=state.get("history", []),
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
    if state.get("governance_probe_detected"):
        notice = (
            "Seluruh akses data dibatasi pada dataset governed; tidak ada data di luar itu yang dapat ditampilkan."
            if _resolve_language(state.get("question", ""), language) == "id"
            else "All data access stays within the governed dataset; nothing outside it can be shown."
        )
        answer = answer.model_copy(update={"caveats": [notice, *answer.caveats][:12]})
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


_GREETING_TERMS = (
    "halo", "hallo", "hai", "hi", "hey", "hello",
    "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
    "good morning", "good afternoon", "good evening",
    "apa kabar", "how are you", "terima kasih", "thank you", "thanks", "makasih",
)


def _is_greeting(question: str) -> bool:
    q = question.lower().strip()
    return any(_contains_alias(q, term) for term in _GREETING_TERMS)


async def direct_chat(state: GraphState) -> GraphState:
    """Handles the "conversational" intent: greetings, small talk, questions
    about the assistant itself, or anything else that isn't a data question.
    Calls the LLM for a natural reply (see LLMProvider.generate_conversational_reply)
    instead of a fixed template, so it can actually respond to whatever was
    asked ("bisa bahasa indonesia?", "siapa kamu?", "terima kasih") rather
    than only recognizing a hardcoded greeting and defaulting to a generic
    "ask an analytical question" message for everything else."""
    language = state.get("language", "auto")
    try:
        result = await get_llm_provider().generate_conversational_reply(
            state["question"], language=language, conversation_history=state.get("history", []), trace_id=state.get("trace_id", ""),
        )
        summary = result.reply.message
    except LLMProviderError:
        summary = (
            "Halo, senang bisa bantu! Aku SCAN, siap gali data komersial bareng kamu. "
            "Coba tanya soal performa sales di suatu wilayah, forecast bulan depan, atau posisi produk dibanding kompetitor ya."
            if _resolve_language(state["question"], language) == "id"
            else "Hey there! I'm SCAN, happy to dig into commercial data with you. "
            "Try asking about sales performance in a region, a forecast, or how a product stacks up against competitors."
        )
    answer = ExecutiveAnswer(summary=summary, drivers=[], recommended_actions=[])
    return {**state, "answer": answer.model_dump(), "chart_spec": {"type": "none", "title": "", "x": [], "series": []}, "ui_actions": [], "resolved_state": state.get("dashboard_state") or {}, "status": "ok"}


async def forecast(state: GraphState) -> GraphState:
    project = load_semantic_project()
    intent = resolve_forecast_intent(state["question"], state.get("dashboard_state") or {}, project)
    lookup = ForecastTool().get_sales_forecast(intent)
    resolved_state = state.get("dashboard_state") or {}
    if lookup.status == "FORECAST_NOT_AVAILABLE":
        requested = intent.forecast_period.strftime("%B %Y")
        current_range = project.resolution.period_ranges.get("current_month")
        latest_actual = (date.fromisoformat(current_range.end) - timedelta(days=1)).isoformat() if current_range else "unknown"
        summary = (
            f"Forecast untuk {requested} belum tersedia. Data aktual terakhir tersedia sampai {latest_actual}. Tidak ada angka forecast yang dibuat sebagai pengganti."
            if _resolve_language(state["question"], state.get("language", "auto")) == "id"
            else f"The forecast for {requested} is not available. Actual data is available through {latest_actual}. No substitute forecast was generated."
        )
        # No recommended_actions here - there is nothing to act on, this is
        # a plain "the data doesn't exist" fallback, not an analysis with a
        # next step to suggest. A generic "show the last 3 months" action
        # repeated on every unrelated forecast miss read as a templated
        # non-sequitur rather than a real recommendation.
        # caveats intentionally empty - see metric_unavailable's comment above.
        answer = ExecutiveAnswer(
            summary=summary,
            drivers=[],
            recommended_actions=[],
            caveats=[],
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
        conversation_history=state.get("history", []),
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


async def weather(state: GraphState, tool=None) -> GraphState:
    """Return immutable calculated weather evidence; no model-generated joins or values."""
    project = load_semantic_project()
    governance = load_weather_governance(project.project)
    intent = resolve_weather_intent(state["question"], state.get("dashboard_state") or {}, project, governance)
    result = (tool or WeatherAnalysisTool()).analyze(intent)
    rows = [item.model_dump(mode="json") for item in result.evidence]
    language = _resolve_language(state["question"], state.get("language", "auto"))
    if result.status == "EXTERNAL_SIGNAL_NOT_AVAILABLE":
        region = result.requested_region or "requested regions"
        period = result.requested_period.isoformat()
        summary = (
            f"Sinyal cuaca historis untuk {region} pada {period} belum tersedia. Konteks sales historis tetap tersedia dan tidak ada nilai cuaca yang diestimasi."
            if language == "id"
            else f"Historical weather for {region} in {period} is unavailable. Historical sales context remains available and no weather values were estimated."
        )
        # caveats intentionally empty - see metric_unavailable's comment above.
        answer = ExecutiveAnswer(summary=summary, drivers=[], recommended_actions=[], caveats=[])
        return {
            **state, "weather_intent": intent.model_dump(mode="json"), "weather_evidence": result.model_dump(mode="json"),
            "answer": answer.model_dump(), "rows": result.sales_context,
            "chart_spec": {"type": "none", "title": "", "x": [], "series": []}, "ui_actions": [],
            "resolved_state": state.get("dashboard_state") or {}, "status": "fallback", "fallback_used": True,
        }

    first = result.evidence[0]
    relationship = ""
    if first.correlation is not None:
        relationship = (
            f" Korelasi terhitung {first.correlation:.3f} berdasarkan {first.observation_count} observasi selaras."
            if language == "id"
            else f" The calculated correlation is {first.correlation:.3f} across {first.observation_count} aligned observations."
        )
    if language == "id":
        summary = (
            f"Sales {first.region_name} berubah {first.sales_change_pct:.2f}% dan {first.weather_metric} berubah "
            f"{first.weather_change:.2f} pada {first.period.isoformat()}.{relationship}"
        )
        caveat = "Terlihat hubungan pada data historis, tetapi belum cukup bukti untuk menyimpulkan sebab-akibat."
    else:
        summary = (
            f"{first.region_name} sales changed {first.sales_change_pct:.2f}% while {first.weather_metric} changed "
            f"{first.weather_change:.2f} in {first.period.isoformat()}.{relationship}"
        )
        caveat = "The historical data shows a relationship, but it is not sufficient to establish causation."
    if result.status == "INSUFFICIENT_OBSERVATIONS":
        caveat = "INSUFFICIENT_OBSERVATIONS. " + caveat
    answer = ExecutiveAnswer(
        summary=summary,
        drivers=[
            f"Governed sales comparison: current={first.sales_current}; previous={first.sales_previous}; change_pct={first.sales_change_pct}",
            f"Governed weather comparison ({first.weather_location}, {first.source}): current={first.weather_current}; previous={first.weather_previous}; change={first.weather_change}",
        ],
        recommended_actions=[], caveats=[caveat, governance.weather.proxy_disclaimer],
    )
    return {
        **state, "weather_intent": intent.model_dump(mode="json"), "weather_evidence": result.model_dump(mode="json"),
        "answer": answer.model_dump(), "rows": rows,
        "chart_spec": {"type": "none", "title": "", "x": [], "series": []}, "ui_actions": [],
        "resolved_state": state.get("dashboard_state") or {}, "status": "ok",
    }


async def market(state: GraphState, tool=None) -> GraphState:
    """Controlled market branch; calculated/persisted evidence remains immutable."""
    project = load_semantic_project()
    governance = load_market_governance(project.project)
    intent = resolve_market_intent(state["question"], state.get("dashboard_state") or {}, project, governance)
    result = (tool or MarketIntelligenceTool()).analyze(intent)
    if result.status != "ok":
        summary = (
            "Sinyal market eksternal yang diminta belum tersedia. Tidak ada angka market atau kompetitor yang diestimasi."
            if _resolve_language(state["question"], state.get("language", "auto")) == "id"
            else "The requested external market signal is unavailable. No market or competitor values were estimated."
        )
        # caveats intentionally empty - see metric_unavailable's comment above.
        answer = ExecutiveAnswer(summary=summary, drivers=[], recommended_actions=[], caveats=[])
        return {
            **state, "market_intent": intent.model_dump(mode="json"), "market_evidence": result.model_dump(mode="json"),
            "answer": answer.model_dump(), "rows": [], "chart_spec": {"type": "none", "title": "", "x": [], "series": []},
            "ui_actions": [], "resolved_state": state.get("dashboard_state") or {}, "status": "fallback", "fallback_used": True,
        }
    rows = result.evidence
    primary_index = next(
        (index for index, row in enumerate(rows) if intent.product_name and row.get("product_name") == intent.product_name),
        0,
    )
    first = rows[primary_index]
    ordered_rows = [first, *rows[:primary_index], *rows[primary_index + 1:]]
    governed_caveats = []
    if result.metadata.get("contains_synthetic_data"):
        governed_caveats.append(governance.synthetic_data_disclaimer)
    governed_caveats.append("Observed relationships do not establish causation; persisted metrics and calculated scores are immutable.")
    payload = TrustedAnalysisPayload(
        question=state["question"], language=state.get("language", "auto"),
        intent=intent.model_dump(mode="json"),
        business_context={
            "provenance": result.metadata,
            "calculated_metrics_immutable": True,
            "instruction": "Explain only from supplied evidence. Never modify metrics, imply measured share, or claim causation.",
        },
        query_result={
            "columns": list(first),
            "rows": ordered_rows,
            "internal_sales_evidence": result.internal_sales_evidence,
        },
        conversation_history=state.get("history", []),
    )
    try:
        explanation = await get_llm_provider().generate_structured(
            payload, language=state.get("language", "auto"), trace_id=state.get("trace_id", ""),
        )
        analysis = explanation.analysis
        model_telemetry = explanation.telemetry.model_dump()
    except LLMProviderError as error:
        analysis = deterministic_grounded_analysis(payload, provider_unavailable=True)
        model_telemetry = {"success": False, "fallback_used": True, "error_code": error.code}
    answer = to_executive_answer(analysis)
    answer.caveats = list(dict.fromkeys([*answer.caveats, *governed_caveats]))
    return {
        **state, "market_intent": intent.model_dump(mode="json"), "market_evidence": result.model_dump(mode="json"),
        "answer": answer.model_dump(), "rows": rows, "chart_spec": {"type": "none", "title": "", "x": [], "series": []},
        "ui_actions": [], "resolved_state": state.get("dashboard_state") or {}, "status": "ok",
        "model_telemetry": model_telemetry,
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
