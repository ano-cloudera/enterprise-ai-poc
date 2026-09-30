from __future__ import annotations

import asyncio
import logging
from time import perf_counter
import uuid

from app.core.config import Settings
from app.core.models import AnalysisOutput, AskDataRequest, AskDataResponse, ChartSpec, QueryData, Timings
from app.db.base import BackendExecutionContext
from app.db.impala_backend import ImpalaBackend
from app.graph.workflow import WorkflowDependencies, build_workflow
from app.llm.registry import ProviderRegistry
from app.semantic.context import SemanticContextService
from app.services.history import ConversationStore
from app.sql.validator import validate_sql


logger = logging.getLogger(__name__)


class ImpalaQueryExecutor:
    def __init__(self, settings: Settings) -> None:
        self.backend = ImpalaBackend(settings)

    async def execute(self, sql: str, request_id: str) -> dict:
        result = await asyncio.to_thread(
            self.backend.execute,
            sql,
            BackendExecutionContext(trace_id=request_id, purpose="ask_data_v2"),
        )
        return {
            "columns": [column.name for column in result.columns],
            "rows": result.records(),
            "row_count": result.row_count,
            "execution_ms": result.telemetry.query_latency_ms,
        }


class ChatService:
    def __init__(
        self,
        settings: Settings,
        *,
        dependencies: WorkflowDependencies | None = None,
        history: ConversationStore | None = None,
    ) -> None:
        self.settings = settings
        context = SemanticContextService(settings.project_root / settings.ossie_project_id)
        self.dependencies = dependencies or WorkflowDependencies(
            semantic_context=context,
            provider_registry=ProviderRegistry(settings),
            query_executor=ImpalaQueryExecutor(settings),
            sql_validator=lambda sql, validation_context: validate_sql(sql, validation_context, max_rows=settings.sql_max_rows),
            validation_context=context,
        )
        self.workflow = build_workflow(self.dependencies)
        self.history = history or ConversationStore(settings.conversation_db_path)

    async def run(self, request: AskDataRequest) -> AskDataResponse:
        request_id = str(uuid.uuid4())
        started = perf_counter()
        initial = {
            **request.model_dump(),
            "request_id": request_id,
            "retry_count": 0,
            "timings": {},
        }
        try:
            state = await self.workflow.ainvoke(initial)
            answer = AnalysisOutput.model_validate(state["answer"])
            chart = ChartSpec.model_validate(state["chart_spec"]) if state.get("chart_spec") else None
            raw_data = state.get("query_result") or {"columns": [], "rows": [], "row_count": 0, "execution_ms": 0}
            timings = {**state.get("timings", {}), "total_ms": round((perf_counter() - started) * 1000, 3)}
            response = AskDataResponse(
                request_id=request_id,
                session_id=request.session_id,
                status=state.get("status", "ERROR"),
                provider=request.provider,
                model=request.model,
                strategy=state.get("strategy", "unsupported"),
                answer=answer,
                data=QueryData.model_validate(raw_data),
                chart_spec=chart,
                timings=Timings.model_validate(timings),
                retry_count=state.get("retry_count", 0),
            )
            self.history.append(request.session_id, request.question, answer, response.data.rows, chart, request.provider, request.model)
            logger.info(
                "ask_data request_id=%s session_id=%s provider=%s model=%s strategy=%s status=%s retry_count=%s timings=%s",
                request_id, request.session_id, request.provider, request.model, response.strategy, response.status, response.retry_count, response.timings.model_dump_json(),
            )
            return response
        except Exception:
            logger.exception("ask_data_failed request_id=%s session_id=%s provider=%s model=%s", request_id, request.session_id, request.provider, request.model)
            elapsed = round((perf_counter() - started) * 1000, 3)
            return AskDataResponse(
                request_id=request_id,
                session_id=request.session_id,
                status="ERROR",
                provider=request.provider,
                model=request.model,
                strategy="unsupported",
                answer=AnalysisOutput(
                    direct_answer="Permintaan tidak dapat diselesaikan dengan aman.",
                    executive_summary="Terjadi kesalahan internal. Gunakan request ID untuk penelusuran operator.",
                    insights=[], business_implications=[], caveats=["Internal error details are not exposed."],
                    data_reference="No result available.", chart_spec=None,
                ),
                data=QueryData(), chart_spec=None, timings=Timings(total_ms=elapsed),
            )

    async def stream(self, request: AskDataRequest):
        labels = {
            "understanding_request": "Understanding request",
            "retrieving_context": "Retrieving semantic context",
            "preparing_query": "Preparing governed query",
            "validating_query": "Validating query",
            "querying_data": "Querying TEMPO data",
            "analyzing_result": "Analyzing result",
        }
        for stage, label in labels.items():
            yield {"type": "progress", "stage": stage, "label": label}
        yield {"type": "done", "response": await self.run(request)}
