from __future__ import annotations

import asyncio
import logging
from time import perf_counter
from typing import Any
import uuid

from app.core.config import Settings
from app.core.models import AnalysisOutput, AskDataRequest, AskDataResponse, ChartSpec, LlmUsage, QueryData, Timings
from app.llm.usage_context import (
    UsageTracker,
    attach_usage_tracker,
    finish_request_usage,
    start_request_usage,
)
from app.services.usage_store import UsageStore
from app.db.base import BackendExecutionContext, DataBackendError
from app.db.impala_backend import ImpalaBackend
from app.graph.workflow import WorkflowDependencies, build_workflow
from app.llm.registry import ProviderRegistry
from app.semantic.context import SemanticContextService
from app.services.history import ConversationStore
from app.services.ask_data_routing import resolve_ask_data_route, v3_agent_available
from app.services.conversational import TurnUnderstanding, understand_turn
from app.services.follow_up import analysis_context_from_history, try_history_only_analysis_resolution
from app.services.question_contextualize import resolve_question_for_pipeline
from app.services.session_context import build_session_frame, capability_session_hint
from app.services.local_agent_client import LocalAgentClient, LocalAgentError
from app.services.ossie_trace import NODE_LABELS, trace_detail
from app.services.v3_answer_polish import polish_v3_answer
from app.services.user_facing_error import explain_failure
from app.sql.validator import validate_sql


logger = logging.getLogger(__name__)

_NO_GOVERNED_REF = "no governed query result attached"


def _normalize_governed_v3_response(response: AskDataResponse) -> AskDataResponse:
    ref = (response.answer.data_reference or "").casefold()
    missing = _NO_GOVERNED_REF in ref and response.data.row_count == 0
    if response.strategy != "governed" or response.status != "SUCCESS" or not missing:
        return response
    caveats = list(response.answer.caveats)
    caveat = (
        "Jawaban belum terhubung ke hasil query governed Impala (tidak ada query_id atau baris data). "
        "Ulangi dengan pertanyaan analitik yang spesifik."
    )
    if caveat not in caveats:
        caveats.insert(0, caveat)
    answer = response.answer.model_copy(update={"caveats": caveats})
    return response.model_copy(update={"status": "NO_DATA", "answer": answer})


def _session_last_metric(history: list[dict]) -> str | None:
    for entry in reversed(history):
        frame = entry.get("session_frame")
        if not isinstance(frame, dict):
            continue
        metric = frame.get("last_metric")
        if isinstance(metric, str) and metric.strip():
            return metric.strip()
    return None


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
        usage_store: UsageStore | None = None,
    ) -> None:
        self.settings = settings
        self.usage_tracker = UsageTracker()
        attach_usage_tracker(self.usage_tracker)
        context = SemanticContextService(settings.project_root / settings.ossie_project_id)
        self.dependencies = dependencies or WorkflowDependencies(
            semantic_context=context,
            provider_registry=ProviderRegistry(settings),
            query_executor=ImpalaQueryExecutor(settings),
            sql_validator=lambda sql, validation_context: validate_sql(sql, validation_context, max_rows=settings.sql_max_rows),
            validation_context=context,
            local_agent_client=LocalAgentClient(settings),
            judge_max_iterations=settings.judge_max_iterations,
            judge_enabled=settings.judge_enabled,
            usage_tracker=self.usage_tracker,
        )
        self.workflow = build_workflow(self.dependencies)
        self.history = history or ConversationStore(settings.conversation_db_path)
        self.usage_store = usage_store or UsageStore(settings.usage_db_path)

    def _resolve_provider(self, request: AskDataRequest, request_id: str):
        provider = self.dependencies.provider_registry.resolve(request.provider, request.model)
        return self.usage_tracker.wrap(provider, request_id)

    def _attach_usage(self, request: AskDataRequest, response: AskDataResponse) -> AskDataResponse:
        acc = finish_request_usage(response.request_id)
        if acc is None:
            return response
        usage = LlmUsage(
            prompt_tokens=acc.prompt_tokens,
            completion_tokens=acc.completion_tokens,
            total_tokens=acc.total_tokens,
            llm_calls=acc.llm_calls,
        )
        self.usage_store.record(
            request_id=response.request_id,
            session_id=request.session_id,
            provider=request.provider,
            model=request.model,
            strategy=str(response.strategy),
            status=str(response.status),
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            llm_calls=usage.llm_calls,
        )
        return response.model_copy(update={"usage": usage})

    def delete_session_history(self, session_id: str) -> int:
        return self.history.delete_session(session_id)

    def _v3_client(self) -> LocalAgentClient | None:
        client = self.dependencies.local_agent_client
        if client is None or not client.enabled:
            return None
        return client

    def _route_for_question(
        self,
        question: str,
        *,
        session_last_metric: str | None = None,
        session_analysis_context: dict[str, Any] | None = None,
        turn_understanding: TurnUnderstanding | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        if session_analysis_context and conversation_history:
            history_only = try_history_only_analysis_resolution(
                question,
                session_analysis_context,
                conversation_history,
                understanding=turn_understanding,
            )
            if history_only:
                route = resolve_ask_data_route(
                    question, self.settings, semantic_resolution=history_only
                )
                return route, history_only
        resolution = self.dependencies.semantic_context.resolve(
            question,
            session_last_metric=session_last_metric,
            session_analysis_context=session_analysis_context,
            turn_understanding=turn_understanding.model_dump() if turn_understanding else None,
        )
        route = resolve_ask_data_route(question, self.settings, semantic_resolution=resolution)
        return route, resolution

    def _session_frame_for_turn(
        self,
        request: AskDataRequest,
        response: AskDataResponse,
        workflow_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolution = (workflow_state or {}).get("semantic_resolution") or {}
        metric = resolution.get("metric")
        dimensions = resolution.get("dimensions")
        return build_session_frame(
            question=request.question,
            status=response.status,
            strategy=response.strategy,
            rows=response.data.rows,
            metric=str(metric) if isinstance(metric, str) else None,
            dimensions=[str(item) for item in dimensions] if isinstance(dimensions, list) else None,
        )

    def _persist_turn(
        self,
        request: AskDataRequest,
        response: AskDataResponse,
        chart: ChartSpec | None,
        *,
        workflow_state: dict[str, Any] | None = None,
    ) -> None:
        self.history.append(
            request.session_id,
            request.question,
            response.answer,
            response.data.rows,
            chart,
            request.provider,
            request.model,
            status=response.status,
            strategy=response.strategy,
            session_frame=self._session_frame_for_turn(request, response, workflow_state),
        )

    async def _run_via_tempo_agent_v3(
        self,
        request: AskDataRequest,
        *,
        request_id: str,
        question: str,
        client: LocalAgentClient,
    ) -> AskDataResponse:
        started = perf_counter()
        try:
            response = await client.ask_data(
                question,
                session_id=request.session_id,
                provider=request.provider,
                model=request.model,
                request_id=request_id,
                answer_language="id",
            )
        except LocalAgentError as exc:
            logger.warning("tempo_agent_v3_primary_failed request_id=%s code=%s", request_id, exc.code)
            provider = self.dependencies.provider_registry.resolve(request.provider, request.model)
            answer = await explain_failure(
                provider=provider,
                question=question,
                failure={"kind": "internal", "code": f"LOCAL_AGENT_{exc.code}"},
                request_id=request_id,
            )
            elapsed = round((perf_counter() - started) * 1000, 3)
            return AskDataResponse(
                request_id=request_id,
                session_id=request.session_id,
                status="ERROR",
                provider=request.provider,
                model=request.model,
                strategy="unsupported",
                answer=answer,
                data=QueryData(),
                chart_spec=None,
                timings=Timings(total_ms=elapsed),
            )
        timings = response.timings.model_copy(update={"total_ms": round((perf_counter() - started) * 1000, 3)})
        response = polish_v3_answer(
            _normalize_governed_v3_response(response.model_copy(update={"timings": timings}))
        )
        self._persist_turn(request, response, response.chart_spec)
        logger.info(
            "ask_data_v3 request_id=%s session_id=%s strategy=%s status=%s total_ms=%s",
            request_id,
            request.session_id,
            response.strategy,
            response.status,
            timings.total_ms,
        )
        return response

    def _routing_mode(self) -> str:
        return (self.settings.ask_data_routing or "auto").strip().lower()

    def _v3_fallback_to_ossie_on_error(self) -> bool:
        return self._routing_mode() == "auto" and not self.settings.local_agent_primary

    async def _understand_turn(
        self,
        request: AskDataRequest,
        conversation_history: list[dict],
        *,
        request_id: str,
    ) -> TurnUnderstanding:
        provider = self._resolve_provider(request, request_id)
        return await understand_turn(
            provider=provider,
            question=request.question,
            conversation_history=conversation_history,
        )

    def _build_initial_state(
        self,
        request: AskDataRequest,
        *,
        request_id: str,
        question: str,
        resolution: dict[str, Any],
        conversation_history: list[dict],
        session_analysis_context: dict[str, Any] | None = None,
        turn_understanding: TurnUnderstanding | None = None,
    ) -> dict[str, Any]:
        state: dict[str, Any] = {
            **request.model_dump(),
            "original_question": request.question,
            "question": question,
            "semantic_resolution": resolution,
            "conversation_history": [
                {"question": item["question"], "answer": item["answer"]}
                for item in conversation_history
            ],
            "session_last_metric": _session_last_metric(conversation_history),
            "request_id": request_id,
            "retry_count": 0,
            "timings": {},
        }
        if turn_understanding is not None:
            payload = turn_understanding.model_dump()
            state["turn_understanding"] = payload
            state["conversational_intent"] = payload
        if session_analysis_context:
            state["session_analysis_context"] = session_analysis_context
        if conversation_history:
            state["session_capability_hint"] = capability_session_hint(conversation_history)
        return state

    def _response_from_state(
        self,
        request: AskDataRequest,
        *,
        request_id: str,
        state: dict[str, Any],
        started: float,
    ) -> AskDataResponse:
        answer = AnalysisOutput.model_validate(state["answer"])
        chart = ChartSpec.model_validate(state["chart_spec"]) if state.get("chart_spec") else None
        raw_data = dict(state.get("query_result") or {"columns": [], "rows": [], "row_count": 0, "execution_ms": 0})
        resolution = state.get("semantic_resolution") if isinstance(state.get("semantic_resolution"), dict) else {}
        plan = state.get("query_plan") if isinstance(state.get("query_plan"), dict) else {}
        metrics = plan.get("metrics") if isinstance(plan.get("metrics"), list) else []
        governed_metric = resolution.get("metric") if resolution.get("status") == "resolved" else None
        if not governed_metric and metrics:
            governed_metric = metrics[0]
        unit_format = None
        if governed_metric:
            definition = resolution.get("definition")
            if isinstance(definition, dict) and definition.get("unit_format"):
                unit_format = definition.get("unit_format")
            else:
                try:
                    unit_format = self.dependencies.semantic_context.metric_definition(str(governed_metric)).get(
                        "unit_format"
                    )
                except Exception:
                    unit_format = None
        if governed_metric:
            raw_data["governed_metric"] = str(governed_metric)
        if unit_format:
            raw_data["unit_format"] = str(unit_format)
        timings = {**state.get("timings", {}), "total_ms": round((perf_counter() - started) * 1000, 3)}
        sql = state.get("validated_sql") or state.get("sql")
        governed_sql = str(sql).strip() if isinstance(sql, str) and sql.strip() else None
        return AskDataResponse(
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
            governed_sql=governed_sql,
        )

    async def _stream_ossie_workflow(
        self,
        request: AskDataRequest,
        *,
        request_id: str,
        question: str,
        resolution: dict[str, Any],
        conversation_history: list[dict],
        session_analysis_context: dict[str, Any] | None = None,
        turn_understanding: TurnUnderstanding | None = None,
    ):
        started = perf_counter()
        initial = self._build_initial_state(
            request,
            request_id=request_id,
            question=question,
            resolution=resolution,
            conversation_history=conversation_history,
            session_analysis_context=session_analysis_context,
            turn_understanding=turn_understanding,
        )
        last_state: dict[str, Any] | None = None
        try:
            async for chunk in self.workflow.astream(initial):
                for node_name, state in chunk.items():
                    last_state = state
                    stage, label = NODE_LABELS.get(node_name, (node_name, node_name.replace("_", " ").title()))
                    detail = trace_detail(node_name, state)
                    yield {
                        "type": "progress",
                        "stage": stage,
                        "label": label,
                        "detail": detail,
                    }
            if last_state is None:
                raise RuntimeError("workflow produced no state")
            response = self._response_from_state(
                request, request_id=request_id, state=last_state, started=started
            )
            response = self._attach_usage(request, response)
            self._persist_turn(request, response, response.chart_spec, workflow_state=last_state)
            yield {"type": "done", "response": response}
        except DataBackendError as exc:
            logger.warning(
                "ask_data_backend_failed request_id=%s safe_error_code=%s",
                request_id,
                exc.code,
            )
            provider = self.dependencies.provider_registry.resolve(request.provider, request.model)
            answer = await explain_failure(
                provider=provider,
                question=request.question,
                failure={"kind": "data_backend", "code": exc.code},
                request_id=request_id,
            )
            elapsed = round((perf_counter() - started) * 1000, 3)
            err = AskDataResponse(
                request_id=request_id,
                session_id=request.session_id,
                status="ERROR",
                provider=request.provider,
                model=request.model,
                strategy="unsupported",
                answer=answer,
                data=QueryData(),
                chart_spec=None,
                timings=Timings(total_ms=elapsed),
            )
            yield {"type": "done", "response": self._attach_usage(request, err)}
        except Exception:
            logger.exception("ask_data_failed request_id=%s", request_id)
            provider = self.dependencies.provider_registry.resolve(request.provider, request.model)
            answer = await explain_failure(
                provider=provider,
                question=request.question,
                failure={"kind": "internal", "code": "UNEXPECTED"},
                request_id=request_id,
            )
            elapsed = round((perf_counter() - started) * 1000, 3)
            err = AskDataResponse(
                request_id=request_id,
                session_id=request.session_id,
                status="ERROR",
                provider=request.provider,
                model=request.model,
                strategy="unsupported",
                answer=answer,
                data=QueryData(),
                chart_spec=None,
                timings=Timings(total_ms=elapsed),
            )
            yield {"type": "done", "response": self._attach_usage(request, err)}

    async def run(self, request: AskDataRequest, *, force_ossie: bool = False) -> AskDataResponse:
        request_id = str(uuid.uuid4())
        start_request_usage(request_id)
        started = perf_counter()
        conversation_history = self.history.load(request.session_id, limit=8)
        session_metric = _session_last_metric(conversation_history)
        session_ctx = analysis_context_from_history(conversation_history)
        turn = await self._understand_turn(request, conversation_history, request_id=request_id)
        question = resolve_question_for_pipeline(request.question, conversation_history, turn)
        route, resolution = self._route_for_question(
            question,
            session_last_metric=session_metric,
            session_analysis_context=session_ctx or None,
            turn_understanding=turn,
            conversation_history=conversation_history,
        )
        if turn.is_conversational:
            logger.info("ask_data_route=conversational request_id=%s session_id=%s", request_id, request.session_id)
            force_ossie = True
        if resolution.get("status") == "history_only":
            force_ossie = True
        if not force_ossie and route == "v3" and v3_agent_available(self.settings):
            client = self._v3_client()
            if client is not None:
                logger.info("ask_data_route=v3 request_id=%s session_id=%s", request_id, request.session_id)
                v3_response = await self._run_via_tempo_agent_v3(
                    request, request_id=request_id, question=question, client=client
                )
                if v3_response.status != "ERROR" or not self._v3_fallback_to_ossie_on_error():
                    return v3_response
                logger.info("ask_data_v3_failed_fallback_ossie request_id=%s", request_id)
        logger.info("ask_data_route=ossie request_id=%s session_id=%s", request_id, request.session_id)
        initial = self._build_initial_state(
            request,
            request_id=request_id,
            question=question,
            resolution=resolution,
            conversation_history=conversation_history,
            session_analysis_context=session_ctx or None,
            turn_understanding=turn,
        )
        try:
            state = await self.workflow.ainvoke(initial)
            response = self._response_from_state(
                request, request_id=request_id, state=state, started=started
            )
            response = self._attach_usage(request, response)
            self._persist_turn(request, response, response.chart_spec, workflow_state=state)
            logger.info(
                "ask_data request_id=%s session_id=%s provider=%s model=%s strategy=%s status=%s retry_count=%s timings=%s turn_rationale=%s",
                request_id, request.session_id, request.provider, request.model, response.strategy, response.status, response.retry_count, response.timings.model_dump_json(), turn.rationale[:120],
            )
            return response
        except DataBackendError as exc:
            # The adapter already emitted safe telemetry. Do not attach the
            # chained driver traceback here because HTTP responses can contain
            # infrastructure details that do not belong in application logs.
            logger.warning(
                "ask_data_backend_failed request_id=%s session_id=%s provider=%s model=%s safe_error_code=%s",
                request_id, request.session_id, request.provider, request.model, exc.code,
            )
            elapsed = round((perf_counter() - started) * 1000, 3)
            provider = self.dependencies.provider_registry.resolve(request.provider, request.model)
            answer = await explain_failure(
                provider=provider,
                question=request.question,
                failure={"kind": "data_backend", "code": exc.code},
                request_id=request_id,
            )
            return AskDataResponse(
                request_id=request_id,
                session_id=request.session_id,
                status="ERROR",
                provider=request.provider,
                model=request.model,
                strategy="unsupported",
                answer=answer,
                data=QueryData(), chart_spec=None, timings=Timings(total_ms=elapsed),
            )
        except Exception:
            logger.exception("ask_data_failed request_id=%s session_id=%s provider=%s model=%s", request_id, request.session_id, request.provider, request.model)
            elapsed = round((perf_counter() - started) * 1000, 3)
            provider = self.dependencies.provider_registry.resolve(request.provider, request.model)
            answer = await explain_failure(
                provider=provider,
                question=request.question,
                failure={"kind": "internal", "code": "UNEXPECTED"},
                request_id=request_id,
            )
            return AskDataResponse(
                request_id=request_id,
                session_id=request.session_id,
                status="ERROR",
                provider=request.provider,
                model=request.model,
                strategy="unsupported",
                answer=answer,
                data=QueryData(), chart_spec=None, timings=Timings(total_ms=elapsed),
            )

    async def stream(self, request: AskDataRequest):
        request_id = str(uuid.uuid4())
        start_request_usage(request_id)
        conversation_history = self.history.load(request.session_id, limit=8)
        session_metric = _session_last_metric(conversation_history)
        session_ctx = analysis_context_from_history(conversation_history)
        turn = await self._understand_turn(request, conversation_history, request_id=request_id)
        question = resolve_question_for_pipeline(request.question, conversation_history, turn)
        route, resolution = self._route_for_question(
            question,
            session_last_metric=session_metric,
            session_analysis_context=session_ctx or None,
            turn_understanding=turn,
            conversation_history=conversation_history,
        )
        skip_v3 = turn.is_conversational or resolution.get("status") == "history_only"
        if skip_v3:
            logger.info("ask_data_route=conversational stream request_id=%s session_id=%s", request_id, request.session_id)
        client = (
            None
            if skip_v3
            else self._v3_client()
            if route == "v3" and v3_agent_available(self.settings)
            else None
        )
        if client is not None:
            logger.info("ask_data_route=v3 stream request_id=%s session_id=%s", request_id, request.session_id)
            try:
                async for event in client.stream_ask_data(
                    question,
                    session_id=request.session_id,
                    provider=request.provider,
                    model=request.model,
                    request_id=request_id,
                    answer_language="id",
                ):
                    if event.get("type") == "progress":
                        yield {
                            "type": "progress",
                            "stage": event.get("stage") or "agent",
                            "label": event.get("label") or "Processing",
                            "detail": event.get("detail"),
                        }
                        continue
                    if event.get("type") == "done":
                        payload = event.get("response") or event
                        if isinstance(payload, dict) and "answer" in payload:
                            response = polish_v3_answer(
                                _normalize_governed_v3_response(AskDataResponse.model_validate(payload))
                            )
                            response = self._attach_usage(request, response)
                            self._persist_turn(request, response, response.chart_spec)
                            yield {"type": "done", "response": response}
                        else:
                            yield event
                        return
                    if "request_id" in event and "answer" in event:
                        response = polish_v3_answer(
                            _normalize_governed_v3_response(AskDataResponse.model_validate(event))
                        )
                        response = self._attach_usage(request, response)
                        self._persist_turn(request, response, response.chart_spec)
                        yield {"type": "done", "response": response}
                        return
                fallback = self._v3_fallback_to_ossie_on_error()
                response = await self._run_via_tempo_agent_v3(
                    request, request_id=request_id, question=question, client=client
                )
                if response.status != "ERROR" or not fallback:
                    yield {"type": "done", "response": response}
                    return
                logger.info("ask_data_v3_stream_fallback_ossie request_id=%s", request_id)
            except LocalAgentError:
                if not self._v3_fallback_to_ossie_on_error():
                    response = await self._run_via_tempo_agent_v3(
                        request, request_id=request_id, question=question, client=client
                    )
                    yield {"type": "done", "response": response}
                    return
                logger.info("ask_data_v3_stream_fallback_ossie request_id=%s", request_id)

        logger.info("ask_data_route=ossie stream request_id=%s session_id=%s", request_id, request.session_id)
        async for event in self._stream_ossie_workflow(
            request,
            request_id=request_id,
            question=question,
            resolution=resolution,
            conversation_history=conversation_history,
            session_analysis_context=session_ctx or None,
            turn_understanding=turn,
        ):
            yield event
