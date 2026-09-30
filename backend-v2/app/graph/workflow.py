from __future__ import annotations

import inspect
import json
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


PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


@dataclass
class WorkflowDependencies:
    semantic_context: Any
    provider_registry: Any
    query_executor: Any
    sql_validator: Callable[[str, Any], ValidatedSQL]
    validation_context: Any


def _elapsed(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _provider(state: AskDataState, deps: WorkflowDependencies) -> LLMProvider:
    return deps.provider_registry.resolve(state["provider"], state["model"])


def _with_timing(state: AskDataState, key: str, value: float) -> dict[str, float]:
    return {**state.get("timings", {}), key: value}


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


def _is_greeting(question: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", " ", question.casefold())
    normalized = " ".join(normalized.split())
    return normalized in {
        "halo", "hai", "hello", "hi", "hey", "selamat pagi",
        "selamat siang", "selamat sore", "selamat malam", "apa kabar",
    }


def build_workflow(deps: WorkflowDependencies):
    async def understand_request(state: AskDataState) -> AskDataState:
        started = perf_counter()
        if _is_greeting(state.get("original_question") or state["question"]):
            try:
                answer = await _provider(state, deps).generate_structured(
                    [
                        {"role": "system", "content": _prompt("global_system.md") + "\n" + _prompt("greeting.md")},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "greeting": state.get("original_question") or state["question"],
                                    "first_turn": not bool(state.get("conversation_history")),
                                    "capabilities": deps.semantic_context.greeting_context(),
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
        if resolution.get("status") == "resolved" and not resolution.get("dimension_mismatch"):
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
            plan = await _provider(state, deps).generate_structured(
                [
                    {"role": "system", "content": _prompt("global_system.md") + "\n" + _prompt("query_planner.md")},
                    {"role": "user", "content": json.dumps({"question": state["question"], "semantic_context": semantic_context}, ensure_ascii=False)},
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
            "semantic_context": deps.semantic_context.planner_context(plan.domains),
            "timings": _with_timing(state, "planning_ms", _elapsed(started)),
        }
        if plan.strategy == "clarification":
            text = plan.clarification_question or "Please clarify the requested metric."
            update.update(status="CLARIFICATION", answer=_safe_answer(text), chart_spec=None, query_result={"columns": [], "rows": [], "row_count": 0, "execution_ms": 0})
        elif plan.strategy == "unsupported":
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
