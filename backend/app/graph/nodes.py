from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from app.core.config import get_settings
from app.forecasting.tool import ForecastTool, resolve_forecast_intent
from app.external_signals.weather.service import load_weather_governance, resolve_weather_intent
from app.external_signals.weather.tool import WeatherAnalysisTool
from app.market_intelligence.service import MarketIntelligenceTool, load_market_governance, resolve_market_intent
from app.llm.models import TrustedAnalysisPayload
from app.core.schemas import ExecutiveAnswer, ChartSpec, ShowTableAction, ui_action_adapter
from app.guardrails.service import GuardrailService
from app.llm.factory import get_llm_provider
from app.llm.payload import deterministic_grounded_analysis, to_executive_answer
from app.llm.providers import LLMProviderError
from app.semantic.loader import load_semantic_project
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
    return {
        **state,
        "intent": "ossie_conversational" if _is_greeting(q) else "ossie_analytical",
    }


def output_guard(state: GraphState) -> GraphState:
    if not state.get("answer"):
        return fallback(state)
    answer = ExecutiveAnswer.model_validate(state["answer"])
    result = guardrails.validate_output(answer)
    if not result.allowed:
        return fallback({**state, "guardrail_error": result.reason or "Output rejected"})
    # contract validation also prevents arbitrary UI action types from escaping
    actions = [ui_action_adapter.validate_python(a) for a in state.get("ui_actions", [])]
    if any(not isinstance(action, ShowTableAction) for action in actions):
        return fallback({**state, "guardrail_error": "Unsupported OSSIE UI action"})
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


async def forecast(state: GraphState) -> GraphState:
    project = load_semantic_project(settings.legacy_synthetic_project_id)
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
    project = load_semantic_project(settings.legacy_synthetic_project_id)
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
    project = load_semantic_project(settings.legacy_synthetic_project_id)
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
