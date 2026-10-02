from __future__ import annotations

import inspect
import json
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from app.core.models import AnalysisOutput, QueryPlan
from app.graph.state import AskDataState
from app.llm.base import LLMProvider, ProviderError
from app.sql.validator import ValidatedSQL


logger = logging.getLogger(__name__)


PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


@dataclass
class WorkflowDependencies:
    semantic_context: Any
    provider_registry: Any
    query_executor: Any
    sql_validator: Callable[[str, Any], ValidatedSQL]
    validation_context: Any
    # Optional: only used when our own planner reports strategy=unsupported.
    # None (the default in every existing test/deployment) skips the
    # fallback node entirely with no behavior change.
    local_agent_client: Any = None


def _elapsed(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _provider(state: AskDataState, deps: WorkflowDependencies) -> LLMProvider:
    return deps.provider_registry.resolve(state["provider"], state["model"])


def _with_timing(state: AskDataState, key: str, value: float) -> dict[str, float]:
    return {**state.get("timings", {}), key: value}


_TABLE_REF_RE = re.compile(r"\bFROM\s+([a-zA-Z_][\w]*\.[a-zA-Z_][\w]*)", re.IGNORECASE)


def _data_reference_from_sql(sql: str) -> str | None:
    """Extract just the gold.<view> name(s) referenced by the executed SQL,
    never the SQL text itself - the analyst's data_reference must stay a
    citation a business user can read, not an implementation detail a raw
    SELECT statement exposes."""
    matches = _TABLE_REF_RE.findall(sql or "")
    if not matches:
        return None
    seen: list[str] = []
    for name in matches:
        if name not in seen:
            seen.append(name)
    return ", ".join(seen)


_UNMET_DIMENSION_LABELS: dict[str, str] = {
    "branch": "cabang/DC partner (B2B branch)",
    "sales_off": "cabang Tempo (sales office)",
    "sales_office": "sales office Tempo",
    "customer": "customer/pelanggan",
    "material": "material/produk/SKU",
    "material_code": "material code",
    "dcname": "nama DC partner",
    "e_store": "outlet/e-store",
    "plu": "PLU",
    "kode_plu": "kode PLU",
    "division": "division",
    "cust_id": "toko/outlet (customer id)",
    "cust_code": "kode customer",
}


def _governed_partial_caveats(resolution: dict[str, Any]) -> list[str]:
    unmet = list(resolution.get("dimension_mismatch") or [])
    if not unmet:
        return []
    metric = str(resolution.get("metric") or "")
    labels = [_UNMET_DIMENSION_LABELS.get(name, name) for name in unmet]
    joined = " dan ".join(labels)
    caveats = [
        "Permintaan breakdown per "
        f"{joined} tidak tersedia pada metrik yang dipilih ({metric}) "
        "dalam katalog governed Q4 2024. Angka di bawah hanya mencakup grain "
        "yang memang didukung metrik ini."
    ]
    if metric == "months_of_stock_cover":
        caveats.append(
            "Cover stok ini proxy stok gudang Tempo terhadap Sell-In per material "
            "(satuan bulan, Oktober–Desember 2024), bukan stok DC/outlet partner "
            "per cabang dan bukan durasi harian."
        )
    return caveats


def _safe_answer(text: str, *, caveats: list[str] | None = None) -> dict[str, Any]:
    return AnalysisOutput(
        direct_answer=text,
        executive_summary=text,
        insights=[],
        business_implications=[],
        caveats=caveats or [],
        data_reference="No query result was used.",
        chart_spec=None,
    ).model_dump()


def _is_conversational_request(question: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", " ", question.casefold())
    normalized = " ".join(normalized.split())
    words = normalized.split()
    greeting = bool(words) and words[0] in {"halo", "hallo", "hai", "hello", "hi", "hey"}
    short_greeting = (greeting and len(words) <= 3) or normalized in {
        "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "apa kabar",
    }
    # A greeting followed directly by a capability question ("hallo kamu
    # bisa bantu apa?") is longer than the plain short_greeting word cap,
    # so it must also be checked by the capability_request pattern below -
    # a leading greeting must not disqualify it just for being longer than
    # a bare "halo"/"hai".
    #
    # "bantu" tolerates common one-letter-swap typos (bintu, bnatu, bantu,
    # etc.) seen in live traffic - this is a fixed, human-curated set of
    # keyboard-adjacent/transposition typos for this one word, not a fuzzy
    # spell-checker, so it can't drift into matching unrelated words.
    help_word = r"b(?:antu|intu|nutu|nautu|antu|nato|antuh|natu)"
    capability_request = bool(
        re.search(rf"\bbisa\s+(?:anda\s+|kamu\s+)?{help_word}\b.*\bapa\b", normalized)
        or re.search(rf"\bkamu\s+{help_word}\s+apa\b", normalized)
        or re.search(r"\bapa\s+(?:lagi|aja|saja)\b", normalized)
        or "selain data" in normalized
        or "bisa keluarin apa" in normalized
        or "bisa ditanyakan" in normalized
        or "contoh pertanyaan" in normalized
        or "apa yang bisa" in normalized
    )
    return short_greeting or capability_request


def _local_agent_second_enabled(deps: WorkflowDependencies) -> bool:
    client = deps.local_agent_client
    return client is not None and getattr(client, "enabled", False)


def _should_try_local_agent_second(state: AskDataState, deps: WorkflowDependencies) -> bool:
    """Primary path first; when LOCAL_AGENT_BASE_URL is set, consult Irvan's
    catalog before showing clarification/unsupported to the user."""
    if state.get("use_local_agent"):
        return True
    return _local_agent_second_enabled(deps)


async def _try_local_agent_fallback(state: AskDataState, deps: WorkflowDependencies) -> dict[str, Any] | None:
    """Second-option consult to TEMPO Local Agent after our primary path
    could not produce a direct answer (unsupported, or selected clarifications).

    Returns an
    AnalysisOutput dict on success, or None on ANY failure (disabled,
    network error, timeout, the local agent itself refusing) - callers
    must treat None as "fall through to the existing unsupported
    message", never as a request-level failure. This function must never
    raise past its own try/except; a broken or unreachable fallback
    service must not turn a normal "unsupported" answer into a 500.
    """
    client = deps.local_agent_client
    if client is None or not getattr(client, "enabled", False):
        return None
    try:
        question = state.get("original_question") or state["question"]
        payload = await client.query(question, answer_language="id")
    except Exception as exc:  # noqa: BLE001 - any failure here must degrade to None, not propagate
        logger.info("local_agent_fallback_failed request_id=%s reason=%s", state.get("request_id"), type(exc).__name__)
        return None

    from app.services.local_agent_client import markdown_to_plain_answer

    markdown = str(payload.get("final_response_markdown") or "")
    text = markdown_to_plain_answer(markdown)
    if not text:
        return None
    query_ids = payload.get("resolved_query_ids") or []
    reference = f"TEMPO Local Agent (separate governed catalog) - query: {', '.join(query_ids)}" if query_ids else "TEMPO Local Agent (separate governed catalog)."
    return AnalysisOutput(
        direct_answer=text,
        executive_summary=text,
        insights=[],
        business_implications=[],
        caveats=[
            "Jawaban ini berasal dari sistem governed terpisah (TEMPO Local Agent), "
            "bukan dari katalog metric utama TEMPO Scan - dapat memiliki definisi "
            "atau cakupan yang sedikit berbeda. Sifatnya eksploratif."
        ],
        data_reference=reference,
        chart_spec=None,
    ).model_dump()


def build_workflow(deps: WorkflowDependencies):
    async def understand_request(state: AskDataState) -> AskDataState:
        started = perf_counter()
        original_question = state.get("original_question") or state["question"]
        if _is_conversational_request(original_question):
            try:
                answer = await _provider(state, deps).generate_structured(
                    [
                        {"role": "system", "content": _prompt("global_system.md") + "\n" + _prompt("greeting.md")},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "question": original_question,
                                    "first_turn": not bool(state.get("conversation_history")),
                                    "conversation_history": state.get("conversation_history", []),
                                    "capabilities": deps.semantic_context.guidance_context(original_question),
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                    AnalysisOutput,
                    temperature=0.4,
                    max_tokens=900,
                )
            except ProviderError:
                answer = AnalysisOutput(
                    direct_answer="Halo! Senang bisa bantu 👋",
                    executive_summary="Saya siap membantu analisis data komersial TEMPO untuk periode Q4 2024.",
                    insights=["Kamu bisa mulai dari Gross Sales, Sell-In, Sell-Out, stok, atau Service Level."],
                    business_implications=[],
                    caveats=["Cakupan data tersedia untuk Oktober–Desember 2024."],
                    data_reference="TEMPO governed capability catalog.",
                    chart_spec=None,
                )
            return {
                **state,
                "request_id": state.get("request_id") or str(uuid.uuid4()),
                "status": "SUCCESS",
                "strategy": "conversational",
                "answer": answer.model_dump(),
                "chart_spec": None,
                "query_result": {"columns": [], "rows": [], "row_count": 0, "execution_ms": 0},
                "timings": _with_timing(state, "context_ms", _elapsed(started)),
            }
        resolution = deps.semantic_context.resolve(state["question"])
        update: AskDataState = {
            **state,
            "request_id": state.get("request_id") or str(uuid.uuid4()),
            "semantic_resolution": resolution,
            "retry_count": state.get("retry_count", 0),
            "timings": _with_timing(state, "context_ms", _elapsed(started)),
        }
        if resolution.get("status") == "needs_clarification":
            update.update(
                status="CLARIFICATION",
                strategy="clarification",
                answer=_safe_answer(str(resolution.get("question") or "Please clarify the requested metric.")),
                chart_spec=None,
                query_result={"columns": [], "rows": [], "row_count": 0, "execution_ms": 0},
            )
        return update

    async def plan_query(state: AskDataState) -> AskDataState:
        started = perf_counter()
        resolution = state["semantic_resolution"]
        partial_caveats: list[str] = []
        if resolution.get("status") == "resolved":
            partial_caveats = _governed_partial_caveats(resolution)
            metric = str(resolution["metric"])
            dimensions = resolution.get("dimensions")
            governed_sql = (
                deps.semantic_context.compile_governed(metric, state["question"], dimensions)
                if dimensions is not None
                else deps.semantic_context.compile_governed(metric, state["question"])
            )
            plan = QueryPlan(
                strategy="governed",
                domains=[str(resolution.get("definition", {}).get("base_dataset") or "")],
                metrics=[metric],
                sql=governed_sql,
            )
        else:
            semantic_context = deps.semantic_context.planner_context()
            # Resolved metrics (including partial dimension coverage) always
            # take the governed compile path above. Hints here are only for
            # fallback/multi_concept cases where the planner must choose.
            resolver_hint: dict[str, Any] = {}
            if resolution.get("status") == "fallback" and resolution.get("reason") == "multi_concept_metric_mismatch":
                resolver_hint = {
                    "requested_concepts": resolution.get("requested_concepts"),
                    "candidate_metric_for_one_concept": resolution.get("candidate_metric"),
                    "note": "The question asks about multiple distinct concepts that no single governed metric covers together. Check semantic_context.metrics for a separate governed metric per concept and use sql_fallback to combine them if each concept has its own approved metric/view, or governed per metric in sequence - do not choose unsupported just because one metric can't cover every concept at once.",
                }
            plan = await _provider(state, deps).generate_structured(
                [
                    {"role": "system", "content": _prompt("global_system.md") + "\n" + _prompt("query_planner.md")},
                    {"role": "user", "content": json.dumps({"question": state["question"], "semantic_context": semantic_context, "resolver_hint": resolver_hint or None}, ensure_ascii=False)},
                ],
                QueryPlan,
                temperature=0,
                max_tokens=1800,
            )
        update: AskDataState = {
            **state,
            "strategy": plan.strategy,
            "query_plan": plan.model_dump(),
            "sql": plan.sql or "",
            "governed_partial_caveats": partial_caveats,
            "semantic_context": deps.semantic_context.planner_context(plan.domains),
            "timings": _with_timing(state, "planning_ms", _elapsed(started)),
        }
        if plan.strategy == "clarification":
            text = plan.clarification_question or "Please clarify the requested metric."
            update.update(status="CLARIFICATION", answer=_safe_answer(text), chart_spec=None, query_result={"columns": [], "rows": [], "row_count": 0, "execution_ms": 0})
            if _should_try_local_agent_second(state, deps):
                fallback_answer = await _try_local_agent_fallback(state, deps)
                if fallback_answer is not None:
                    update.update(
                        status="SUCCESS",
                        strategy="local_agent_exploratory",
                        answer=fallback_answer,
                        chart_spec=None,
                        query_result={"columns": [], "rows": [], "row_count": 0, "execution_ms": 0},
                    )
        elif plan.strategy == "unsupported":
            fallback_answer = (
                await _try_local_agent_fallback(state, deps)
                if _should_try_local_agent_second(state, deps)
                else None
            )
            if fallback_answer is not None:
                update.update(
                    status="SUCCESS",
                    strategy="local_agent_exploratory",
                    answer=fallback_answer,
                    chart_spec=None,
                    query_result={"columns": [], "rows": [], "row_count": 0, "execution_ms": 0},
                )
            else:
                update.update(status="UNSUPPORTED", answer=_safe_answer("Data yang diminta tidak tersedia pada scope TEMPO saat ini."), chart_spec=None, query_result={"columns": [], "rows": [], "row_count": 0, "execution_ms": 0})
        return update

    async def validate_query(state: AskDataState) -> AskDataState:
        started = perf_counter()
        result = deps.sql_validator(state.get("sql", ""), deps.validation_context)
        retry_count = state.get("retry_count", 0)
        if not result.valid and retry_count < 1:
            repair = await _provider(state, deps).generate_structured(
                [
                    {"role": "system", "content": _prompt("global_system.md") + "\n" + _prompt("sql_repair.md")},
                    {"role": "user", "content": json.dumps({"invalid_sql": state.get("sql"), "error": result.error, "semantic_context": state.get("semantic_context")}, ensure_ascii=False)},
                ],
                QueryPlan,
                temperature=0,
                max_tokens=1200,
            )
            retry_count += 1
            result = deps.sql_validator(repair.sql or "", deps.validation_context)
            state = {**state, "query_plan": repair.model_dump(), "sql": repair.sql or ""}
        update: AskDataState = {
            **state,
            "retry_count": retry_count,
            "validation_error": result.error or "",
            "timings": _with_timing(state, "validation_ms", _elapsed(started)),
        }
        if result.valid:
            update["validated_sql"] = result.sql or ""
        else:
            update.update(
                status="ERROR",
                answer=_safe_answer("Query tidak dapat divalidasi dengan aman.", caveats=[result.error or "Invalid SQL"]),
                chart_spec=None,
                query_result={"columns": [], "rows": [], "row_count": 0, "execution_ms": 0},
            )
        return update

    async def execute_query(state: AskDataState) -> AskDataState:
        started = perf_counter()
        result = deps.query_executor.execute(state["validated_sql"], state["request_id"])
        if inspect.isawaitable(result):
            result = await result
        update: AskDataState = {
            **state,
            "query_result": result,
            "timings": _with_timing(state, "query_ms", _elapsed(started)),
        }
        if not result.get("rows"):
            update.update(
                status="NO_DATA",
                answer=_safe_answer("Tidak ada data yang cocok untuk pertanyaan dan filter tersebut."),
                chart_spec=None,
            )
        return update

    async def analyze_result(state: AskDataState) -> AskDataState:
        started = perf_counter()
        analysis = await _provider(state, deps).generate_structured(
            [
                {"role": "system", "content": _prompt("global_system.md") + "\n" + _prompt("result_analyst.md")},
                {"role": "user", "content": json.dumps({"question": state["question"], "query_plan": state.get("query_plan"), "semantic_context": state.get("semantic_context"), "query_result": state["query_result"]}, ensure_ascii=False, default=str)},
            ],
            AnalysisOutput,
            temperature=0.1,
            max_tokens=1800,
        )
        chart = analysis.chart_spec
        columns = set(state["query_result"].get("columns", []))
        if chart and any(field and field not in columns for field in (chart.x, chart.y, chart.series)):
            chart = None
            analysis = analysis.model_copy(update={"chart_spec": None})
        # Always override data_reference with just the view name(s) parsed
        # from the executed SQL - never trust the model to keep the raw
        # SQL text out of a field meant to be a plain-language citation,
        # regardless of what result_analyst.md asks for.
        schema_reference = _data_reference_from_sql(state.get("validated_sql") or state.get("sql") or "")
        if schema_reference:
            analysis = analysis.model_copy(update={"data_reference": schema_reference})
        extra = list(state.get("governed_partial_caveats") or [])
        if extra:
            merged = list(analysis.caveats)
            for item in extra:
                if item not in merged:
                    merged.append(item)
            analysis = analysis.model_copy(update={"caveats": merged})
        return {
            **state,
            "status": "SUCCESS",
            "answer": analysis.model_dump(),
            "chart_spec": chart.model_dump() if chart else None,
            "timings": _with_timing(state, "analysis_ms", _elapsed(started)),
        }

    def after_understand(state: AskDataState) -> str:
        return "end" if state.get("status") else "plan_query"

    def after_plan(state: AskDataState) -> str:
        return "end" if state.get("status") else "validate_query"

    def after_validate(state: AskDataState) -> str:
        return "end" if state.get("status") else "execute_query"

    def after_execute(state: AskDataState) -> str:
        return "end" if state.get("status") else "analyze_result"

    graph = StateGraph(AskDataState)
    graph.add_node("understand_request", understand_request)
    graph.add_node("plan_query", plan_query)
    graph.add_node("validate_query", validate_query)
    graph.add_node("execute_query", execute_query)
    graph.add_node("analyze_result", analyze_result)
    graph.add_edge(START, "understand_request")
    graph.add_conditional_edges("understand_request", after_understand, {"plan_query": "plan_query", "end": END})
    graph.add_conditional_edges("plan_query", after_plan, {"validate_query": "validate_query", "end": END})
    graph.add_conditional_edges("validate_query", after_validate, {"execute_query": "execute_query", "end": END})
    graph.add_conditional_edges("execute_query", after_execute, {"analyze_result": "analyze_result", "end": END})
    graph.add_edge("analyze_result", END)
    return graph.compile()
