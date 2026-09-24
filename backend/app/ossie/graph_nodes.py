from __future__ import annotations

import logging
from typing import Any

from langdetect import DetectorFactory, LangDetectException, detect

from app.core.schemas import ExecutiveAnswer
from app.graph.state import GraphState

from .service import OssieQueryRequest, get_tempo_ossie_service


logger = logging.getLogger(__name__)

# langdetect samples character n-grams and needs a handful of words to be
# reliable - fed a single greeting word ("Halo", "Hi") it guesses almost at
# random (observed returning "so", "fi", "nl" for those). Deterministic
# results across runs/processes also require a fixed seed (its default
# algorithm is otherwise randomized).
DetectorFactory.seed = 0

# Exact/near-exact greeting and small-talk phrases - checked first because
# they're exactly the short inputs langdetect is unreliable on, and because
# the greeting response text itself is a fixed spec (see
# _FIRST_GREETING_EXAMPLES_ID/EN below), not something a classifier's
# confidence should decide between.
_ID_GREETING_MARKERS = (
    "halo", "hai", "selamat pagi", "selamat siang", "selamat sore",
    "selamat malam", "terima kasih", "apa kabar", "makasih",
)
_EN_GREETING_MARKERS = (
    "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
    "how are you", "thanks", "thank you",
)


def _language(question: str) -> str:
    lowered = question.casefold().strip()
    if any(marker in lowered for marker in _ID_GREETING_MARKERS):
        return "id"
    if any(marker in lowered for marker in _EN_GREETING_MARKERS):
        return "en"
    # Longer, keyword-less questions ("Bisakah Anda menjelaskan...") fall
    # through to actual language detection rather than an ever-growing
    # keyword list, which is what left the "Halo" gap in the first place.
    try:
        detected = detect(question)
    except LangDetectException:
        return "en"
    return "id" if detected == "id" else "en"


def _infer_dimensions(question: str, allowed: set[str]) -> list[str]:
    lowered = question.casefold()
    dimensions: list[str] = []
    rules = (
        ("calmonth", ("bulan", "bulanan", "month", "trend", "tren")),
        ("material", ("material", "sku", "produk")),
        ("customer", ("customer", "pelanggan")),
        ("sales_office", ("sales office", "cabang", "office")),
        ("fill_rate_band", ("fill rate band", "kategori fill", "low fill")),
        ("reporting_period", ("q4", "quarter", "kuartal")),
    )
    for dimension, terms in rules:
        if dimension in allowed and any(term in lowered for term in terms):
            dimensions.append(dimension)

    ranking_terms = ("mana", "top", "tertinggi", "terendah", "terbesar", "terlama")
    if any(term in lowered for term in ranking_terms):
        business_dimensions = [
            dimension
            for dimension in ("material", "customer", "sales_office", "fill_rate_band")
            if dimension in allowed
        ]
        if business_dimensions and not any(item in dimensions for item in business_dimensions):
            dimensions.append(business_dimensions[0])
    return dimensions


def _infer_filters(question: str, allowed: set[str]) -> dict[str, list[Any]]:
    lowered = question.casefold()
    filters: dict[str, list[Any]] = {}
    if "fill_rate_band" in allowed:
        if "low fill" in lowered:
            filters["fill_rate_band"] = ["low_fill"]
        elif "medium fill" in lowered:
            filters["fill_rate_band"] = ["medium_fill"]
        elif "high fill" in lowered:
            filters["fill_rate_band"] = ["high_fill"]
        elif "unknown" in lowered or "tidak tersedia" in lowered:
            filters["fill_rate_band"] = ["unknown"]
    return filters


def _scope_caveats(definition: dict[str, Any]) -> list[str]:
    caveats = ["Governed data scope: October–December 2024."]
    approval = definition.get("business_approval_status")
    if approval == "pending_business_confirmation":
        caveats.append("This is a technically validated candidate metric pending TEMPO business confirmation.")
    elif approval == "internal_technical_review":
        caveats.append("This is an internal technical/data-quality metric, not an official business KPI.")
    context = definition.get("ai_context") or {}
    instructions = context.get("instructions") if isinstance(context, dict) else None
    if instructions:
        caveats.append(str(instructions))
    return caveats


# Fixed 4-question sample shown on the first greeting of a session - chosen
# to span the breadth of governed capability (executive trend, material
# service level, Sell-In/Sell-Out comparison, sales office operations)
# rather than whatever happens to sort first in golden_questions.yaml, so a
# new user immediately sees the range of what SCAN can answer.
_FIRST_GREETING_EXAMPLES_ID = (
    "Bagaimana tren Gross Sales selama Q4?",
    "Material mana dengan Fill Rate terendah?",
    "Bagaimana perbandingan Sell-In dan Sell-Out?",
    "Sales office mana dengan picking delay tertinggi?",
)
_FIRST_GREETING_EXAMPLES_EN = (
    "How has Gross Sales trended over Q4?",
    "Which material has the lowest Fill Rate?",
    "How do Sell-In and Sell-Out compare?",
    "Which sales office has the highest picking delay?",
)


def ossie_conversational(state: GraphState) -> GraphState:
    language = _language(state["question"])
    # The full "here's what I can do" greeting is only useful the first time
    # a session says hello - state["history"] is empty exactly then, since
    # it holds prior turns from this same session. A later "halo" mid-chat
    # gets a short, natural reply instead of repeating the whole pitch.
    is_first_turn = not state.get("history")

    if is_first_turn:
        if language == "id":
            summary = (
                "Halo, saya SCAN. Saya dapat membantu analisis data Tempo periode "
                "Oktober–Desember 2024 terkait Sell-In, Sell-Out, Material 360, "
                "Service Level, stok gudang, performa sales office, dan "
                "rekonsiliasi customer."
            )
            actions = list(_FIRST_GREETING_EXAMPLES_ID)
            caveat = (
                "Untuk pertanyaan di luar cakupan data, saya akan menjelaskan "
                "informasi yang belum tersedia. Periode data yang tersedia: "
                "Oktober–Desember 2024."
            )
        else:
            summary = (
                "Hello, I'm SCAN. I can help analyze Tempo's October–December "
                "2024 data covering Sell-In, Sell-Out, Material 360, Service "
                "Level, warehouse stock, sales office performance, and customer "
                "reconciliation."
            )
            actions = list(_FIRST_GREETING_EXAMPLES_EN)
            caveat = (
                "For questions outside this data's scope, I'll explain what "
                "isn't available. Available reporting period: October–December "
                "2024."
            )
    else:
        summary = (
            "Halo lagi! Ada yang bisa saya bantu soal data Tempo Q4 2024?"
            if language == "id"
            else "Hey again! Anything else I can help with on Tempo's Q4 2024 data?"
        )
        actions = []
        caveat = (
            "Periode data yang tersedia: Oktober–Desember 2024."
            if language == "id"
            else "Available reporting period: October–December 2024."
        )

    answer = ExecutiveAnswer(
        summary=summary,
        drivers=[],
        recommended_actions=actions,
        caveats=[caveat],
    )
    return {
        **state,
        "intent": "conversational",
        "answer": answer.model_dump(),
        "rows": [],
        "chart_spec": {"type": "none", "title": "", "x": [], "series": []},
        "ui_actions": [],
        "resolved_state": state.get("dashboard_state") or {},
        "capability_status": "supported",
        "scope_notice": "Governed TEMPO data scope: October–December 2024.",
        "status": "ok",
        "fallback_used": False,
    }


async def ossie_analytical(state: GraphState) -> GraphState:
    service = get_tempo_ossie_service()
    resolution = await service.resolve_with_llm_fallback(state["question"], trace_id=state.get("trace_id", ""))
    language = _language(state["question"])

    if resolution["status"] == "needs_clarification":
        answer = ExecutiveAnswer(
            summary=resolution["question"],
            drivers=[str(option.get("label")) for option in resolution.get("options", [])],
            recommended_actions=[],
            caveats=[],
        )
        return {
            **state,
            "answer": answer.model_dump(),
            "rows": [],
            "chart_spec": {"type": "none", "title": "", "x": [], "series": []},
            "ui_actions": [],
            "resolved_state": state.get("dashboard_state") or {},
            "capability_status": "ambiguous",
            "scope_notice": "A governed metric clarification is required.",
            "status": "fallback",
            "fallback_used": True,
        }

    if resolution["status"] != "resolved":
        examples = resolution.get("capabilities", {}).get("examples", [])[:3]
        summary = (
            "Pertanyaan tersebut belum tersedia pada semantic scope Q4 2024."
            if language == "id"
            else "That question is not available in the governed Q4 2024 semantic scope."
        )
        answer = ExecutiveAnswer(
            summary=summary,
            drivers=[],
            recommended_actions=examples,
            caveats=["SCAN did not generate free SQL or invent a metric."],
        )
        return {
            **state,
            "answer": answer.model_dump(),
            "rows": [],
            "chart_spec": {"type": "none", "title": "", "x": [], "series": []},
            "ui_actions": [],
            "resolved_state": state.get("dashboard_state") or {},
            "capability_status": "unsupported",
            "scope_notice": "Governed TEMPO data scope: October–December 2024.",
            "status": "fallback",
            "fallback_used": True,
        }

    metric = resolution["metric"]
    definition = resolution["definition"]
    allowed = set(definition["allowed_dimensions"])
    dimensions = _infer_dimensions(state["question"], allowed)
    filters = _infer_filters(state["question"], allowed)
    lowered = state["question"].casefold()
    order = "asc" if any(term in lowered for term in ("terendah", "terkecil", "lowest", "bottom")) else "desc"
    request = OssieQueryRequest(
        metric=metric,
        dimensions=dimensions,
        filters=filters,
        start_calmonth=202410 if "calmonth" in _dataset_fields(service, definition) else None,
        end_calmonth=202412 if "calmonth" in _dataset_fields(service, definition) else None,
        order=order,
        limit=50,
    )

    try:
        result = service.execute_query(request, trace_id=state.get("trace_id", ""))
    except Exception:
        logger.exception("Ossie governed execution failed trace_id=%s", state.get("trace_id"))
        answer = ExecutiveAnswer(
            summary=(
                "Analisis governed tidak dapat dijalankan saat ini."
                if language == "id"
                else "The governed analysis could not be executed right now."
            ),
            drivers=[],
            recommended_actions=[],
            caveats=["No ungoverned fallback query was attempted."],
        )
        return {
            **state,
            "answer": answer.model_dump(),
            "rows": [],
            "chart_spec": {"type": "none", "title": "", "x": [], "series": []},
            "ui_actions": [],
            "resolved_state": state.get("dashboard_state") or {},
            "capability_status": "partial",
            "scope_notice": "Governed execution was unavailable; no ungoverned fallback ran.",
            "status": "fallback",
            "fallback_used": True,
        }

    rows = result["rows"]
    if not dimensions and rows:
        value = rows[0].get("metric_value")
        summary = (
            f"{definition['description']}: {value}"
            if language == "en"
            else f"{definition['description']}: {value}"
        )
    else:
        summary = (
            f"Analisis {definition['description']} menghasilkan {len(rows)} baris governed."
            if language == "id"
            else f"The governed {definition['description']} analysis returned {len(rows)} rows."
        )
    answer = ExecutiveAnswer(
        summary=summary,
        drivers=[
            f"Metric: {definition['metric_id']} · {metric}",
            f"Source: {result['semantic_plan']['source_view']}",
            f"Grain: {result['semantic_plan'].get('grain')}",
        ],
        recommended_actions=[],
        caveats=_scope_caveats(definition),
    )
    chart_type = "line" if dimensions == ["calmonth"] else ("bar" if len(dimensions) == 1 else "table")
    chart_spec = {
        "type": chart_type if rows else "none",
        "title": definition["description"] or metric,
        "x": [str(row.get(dimensions[0], "")) for row in rows] if len(dimensions) == 1 else [],
        "series": (
            [{"name": definition["metric_id"], "data": [row.get("metric_value") for row in rows]}]
            if len(dimensions) == 1
            else []
        ),
        "dimension": dimensions[0] if len(dimensions) == 1 else None,
        "metric": metric,
        "target": "chat",
    }
    ui_actions = (
        [{"type": "SHOW_TABLE", "target": "chat", "value": {"columns": list(rows[0]) if rows else []}}]
        if rows
        else []
    )
    prior = state.get("dashboard_state") or {}
    resolved_state = {
        **prior,
        "metric": metric,
        "dimension": dimensions[0] if dimensions else prior.get("dimension", "calmonth"),
        "date_range": {"preset": "q4_2024", "start": None, "end": None},
    }
    return {
        **state,
        "semantic_resolution": resolution,
        "semantic_plan": result["semantic_plan"],
        "analytical_intent": request.model_dump(),
        "sql": result["sql"],
        "validated_sql": result["sql"],
        "rows": rows,
        "answer": answer.model_dump(),
        "chart_spec": chart_spec,
        "ui_actions": ui_actions,
        "resolved_state": resolved_state,
        "data_telemetry": result.get("telemetry", {}),
        "capability_status": "supported",
        "scope_notice": "Governed TEMPO data scope: October–December 2024.",
        "status": "ok",
        "fallback_used": False,
    }


def _dataset_fields(service, definition: dict[str, Any]) -> set[str]:
    dataset = definition["base_dataset"]
    return set(service.registry.dataset_fields[dataset])

