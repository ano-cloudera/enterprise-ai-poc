from __future__ import annotations

import logging
import uuid
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.config import Settings
from app.core.models import (
    AgentFinish,
    AgentFinishAnswer,
    AgentToolCall,
    AnalysisOutput,
    AskDataRequest,
    AskDataResponse,
    ChartSpec,
    QueryData,
    Timings,
)
from app.db.duckdb_catalog import DuckDBCatalog, observation_json
from app.llm.base import LLMProvider, ProviderError
from app.llm.registry import ProviderRegistry


logger = logging.getLogger(__name__)


def _provider_error_message(code: str) -> str:
    if code in {"credit_balance_exhausted", "insufficient_quota"}:
        return (
            "Saldo/kuota API OpenAI habis (HTTP 429). Isi ulang billing OpenAI atau "
            "pakai Gemini (GEMINI_API_KEY) / Qwen di backend-v3/.env."
        )
    if code in {"API_KEY_INVALID", "PERMISSION_DENIED", "403"}:
        return "API key Gemini/OpenAI ditolak — periksa GEMINI_API_KEY dan model id di .env."
    if code == "TIMEOUT":
        return "Model timeout — coba lagi atau kurangi kompleksitas pertanyaan."
    if code == "INVALID_STRUCTURED_OUTPUT":
        return "Model mengembalikan JSON tidak valid — coba ulang atau ganti model."
    return f"Model provider gagal ({code}). Periksa API key, model id, dan base URL."


def _load_system_prompt(settings: Settings) -> str:
    domain_doc = (settings.knowledge_dir / "tempo_domains.md").read_text(encoding="utf-8")
    return f"""You are TEMPO commercial analytics copilot (exploratory local mode).

You may call tools to inspect DuckDB silver sample data, then finish with a grounded AnalysisOutput JSON when you have enough evidence.

Tools (return JSON matching AgentToolCall until you have enough evidence, then call finish):
- list_tables — no args
- describe_table — set table to qualified name e.g. silver.sales_oct_dec_2024
- run_sql — set sql to a single SELECT (silver schema only, explicit columns, LIMIT)
- finish — stop exploring; you will be asked for AnalysisOutput next

Rules:
- Use tools before guessing schema. Start with list_tables or describe_table when unsure.
- Only read-only SQL on silver.* tables. Never SELECT *.
- Q4 2024 scope unless the user explicitly widens it.
- Never invent numbers — only values returned by run_sql.
- Include caveats: local sample DuckDB, not official Impala/gold KPIs.
- Prefer Indonesian for answers when the user writes in Indonesian.

Domain reference:
{domain_doc}
"""


class ExploratoryAgentService:
    def __init__(self, settings: Settings, *, catalog: DuckDBCatalog | None = None) -> None:
        self.settings = settings
        self.catalog = catalog or DuckDBCatalog(settings.duckdb_path, sql_max_rows=settings.sql_max_rows)
        self.registry = ProviderRegistry(settings)

    async def run(self, request: AskDataRequest) -> AskDataResponse:
        request_id = str(uuid.uuid4())
        started = perf_counter()
        provider = self.registry.resolve(request.provider, request.model)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _load_system_prompt(self.settings)},
            {"role": "user", "content": request.question},
        ]
        steps_log: list[dict[str, Any]] = []
        last_query: dict[str, Any] = {"columns": [], "rows": [], "row_count": 0, "execution_ms": 0}
        query_ms = 0.0
        agent_started = perf_counter()

        for step_idx in range(self.settings.agent_max_steps):
            try:
                tool_call = await provider.generate_structured(
                    messages,
                    AgentToolCall,
                    temperature=0.1,
                    max_tokens=min(self.settings.llm_max_tokens, 1200),
                )
            except ProviderError as exc:
                return self._error_response(
                    request_id,
                    request,
                    started,
                    _provider_error_message(exc.code),
                )

            steps_log.append({"step": step_idx + 1, "tool_call": tool_call.model_dump()})

            if tool_call.tool == "finish":
                steps_log[-1]["early_finish"] = True
                break

            if tool_call.tool == "list_tables":
                obs = {"tables": self.catalog.list_tables()}
                messages.append({"role": "assistant", "content": observation_json(tool_call.model_dump())})
                messages.append({"role": "user", "content": f"Tool result list_tables:\n{observation_json(obs)}"})
                continue

            if tool_call.tool == "describe_table":
                table = (tool_call.table or "").strip()
                try:
                    obs = self.catalog.describe_table(table)
                except ValueError as exc:
                    obs = {"error": str(exc)}
                messages.append({"role": "assistant", "content": observation_json(tool_call.model_dump())})
                messages.append({"role": "user", "content": f"Tool result describe_table:\n{observation_json(obs)}"})
                continue

            if tool_call.tool == "run_sql":
                sql = (tool_call.sql or "").strip()
                try:
                    result = self.catalog.run_sql(sql)
                    last_query = result
                    query_ms += float(result.get("execution_ms") or 0)
                    obs = {
                        "sql": result.get("sql"),
                        "columns": result.get("columns"),
                        "row_count": result.get("row_count"),
                        "rows": result.get("rows", [])[:25],
                    }
                except ValueError as exc:
                    obs = {"error": str(exc), "sql": sql}
                messages.append({"role": "assistant", "content": observation_json(tool_call.model_dump())})
                messages.append({"role": "user", "content": f"Tool result run_sql:\n{observation_json(obs)}"})
                continue

        agent_ms = round((perf_counter() - agent_started) * 1000, 3)
        analysis_started = perf_counter()
        messages.append(
            {
                "role": "user",
                "content": (
                    "Stop exploring. Using ONLY tool results above, return finish with a complete AnalysisOutput. "
                    "If evidence is insufficient, say so in direct_answer and caveats. "
                    "Optional chart_spec must reference columns from the last successful query."
                ),
            }
        )
        try:
            finished = await provider.generate_structured(
                messages,
                AgentFinish,
                temperature=0.15,
                max_tokens=self.settings.llm_max_tokens,
            )
        except ProviderError:
            finished = AgentFinish(
                reasoning="fallback",
                tool="finish",
                answer=AgentFinishAnswer(
                    direct_answer="Agent mencapai batas langkah tanpa jawaban final dari model.",
                    executive_summary="Coba pertanyaan lebih sempit atau periksa API LLM.",
                    insights=[],
                    business_implications=[],
                    caveats=[f"Agent steps: {len(steps_log)}", "Local sample DuckDB."],
                    data_reference="silver.* (local sample)",
                ),
            )

        answer = AnalysisOutput(
            **finished.answer.model_dump(),
            chart_spec=None,
        )
        chart = answer.chart_spec
        columns = set(last_query.get("columns") or [])
        if chart and chart.x and chart.y and (chart.x not in columns or chart.y not in columns):
            chart = None
            answer = answer.model_copy(update={"chart_spec": None})

        status = "NO_DATA" if last_query.get("row_count", 0) == 0 and not answer.direct_answer else "SUCCESS"
        if "tidak cukup" in answer.direct_answer.casefold() or "insufficient" in answer.direct_answer.casefold():
            status = "NO_DATA"

        analysis_ms = round((perf_counter() - analysis_started) * 1000, 3)
        total_ms = round((perf_counter() - started) * 1000, 3)

        return AskDataResponse(
            request_id=request_id,
            session_id=request.session_id,
            status=status,
            provider=request.provider,
            model=request.model,
            strategy="exploratory_local",
            answer=answer,
            data=QueryData(
                columns=list(last_query.get("columns") or []),
                rows=list(last_query.get("rows") or []),
                row_count=int(last_query.get("row_count") or 0),
                execution_ms=float(last_query.get("execution_ms") or 0),
            ),
            chart_spec=chart,
            timings=Timings(agent_ms=agent_ms, query_ms=query_ms, analysis_ms=analysis_ms, total_ms=total_ms),
            agent_steps=steps_log,
        )

    def _error_response(
        self,
        request_id: str,
        request: AskDataRequest,
        started: float,
        message: str,
    ) -> AskDataResponse:
        elapsed = round((perf_counter() - started) * 1000, 3)
        return AskDataResponse(
            request_id=request_id,
            session_id=request.session_id,
            status="ERROR",
            provider=request.provider,
            model=request.model,
            strategy="error",
            answer=AnalysisOutput(
                direct_answer=message,
                executive_summary=message,
                insights=[],
                business_implications=[],
                caveats=["Periksa OPENAI_API_KEY / QWEN_API_KEY dan DUCKDB_PATH."],
                data_reference="No result available.",
                chart_spec=None,
            ),
            data=QueryData(),
            chart_spec=None,
            timings=Timings(total_ms=elapsed),
        )

    async def stream(self, request: AskDataRequest):
        labels = [
            ("understanding_request", "Understanding request"),
            ("exploring_schema", "Exploring silver schema"),
            ("running_sql", "Running exploratory SQL"),
            ("analyzing_result", "Analyzing result"),
        ]
        for stage, label in labels:
            yield {"type": "progress", "stage": stage, "label": label}
        yield {"type": "done", "response": await self.run(request)}
