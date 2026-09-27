from __future__ import annotations

import time
import uuid
import logging

from app.core.config import get_settings
from app.core.schemas import (
    ChatMetadata,
    ChatRequest,
    ChatResponse,
    ChartSpec,
    DashboardState,
    ExecutiveAnswer,
    QueryData,
    ui_action_adapter,
)
from app.graph.workflow import workflow
from app.monitoring.store import TelemetryStore
from app.services import agent_studio_client, markdown_chart_adapter
from app.services.conversation_store import ConversationStore


telemetry = TelemetryStore()
conversations = ConversationStore()
logger = logging.getLogger(__name__)


async def run_chat(request: ChatRequest) -> ChatResponse:
    if get_settings().chat_backend == "agent_studio":
        return await _run_chat_agent_studio(request)
    return await _run_chat_graph(request)


async def _run_chat_agent_studio(request: ChatRequest) -> ChatResponse:
    """chat_backend="agent_studio": delegates the answer entirely to the
    deployed Agent Studio workflow (Master -> Data -> Analysis agents) and
    adapts its Markdown output into ChatResponse. See
    app/services/agent_studio_client.py and markdown_chart_adapter.py.

    Deliberately does not touch conversation_store/TelemetryStore's
    intent/validation_status fields the graph path fills in - Agent
    Studio's own trace_id/events are the source of truth for this path, and
    multi-turn memory is Agent Studio's session state, not
    ConversationStore's (see agent_studio_client.run_workflow's context
    param for how a future follow-up turn would be threaded through).
    """
    trace_id = str(uuid.uuid4())
    started = time.perf_counter()
    try:
        result = await agent_studio_client.run_workflow(user_input=request.question)
        parsed = markdown_chart_adapter.parse(result.output, request.question)
        latency_ms = round((time.perf_counter() - started) * 1000)
        telemetry.record(
            trace_id=result.trace_id,
            question=request.question,
            intent="agent_studio",
            status="ok",
            latency_ms=latency_ms,
            metadata={"agent_studio_trace_id": result.trace_id, "event_count": len(result.events)},
        )
        return ChatResponse(
            status="ok",
            question=request.question,
            answer=parsed.answer,
            data=parsed.data,
            chart_spec=parsed.chart_spec,
            ui_actions=[],
            metadata=ChatMetadata(
                trace_id=result.trace_id,
                session_id=request.session_id,
                intent="agent_studio",
                resolved_context=request.context,
                execution_time_ms=latency_ms,
            ),
        )
    except agent_studio_client.AgentStudioError:
        logger.exception("Agent Studio chat backend failed trace_id=%s", trace_id)
        latency_ms = round((time.perf_counter() - started) * 1000)
        telemetry.record(trace_id=trace_id, question=request.question, intent="agent_studio", status="error", latency_ms=latency_ms, metadata={"safe_error": True})
        return ChatResponse(
            status="error",
            question=request.question,
            answer=ExecutiveAnswer(summary="Governed data could not be retrieved right now.", drivers=[], recommended_actions=["Try again in a moment or rephrase the question."], caveats=["Internal error details are not exposed."]),
            data=QueryData(),
            chart_spec=None,
            ui_actions=[],
            metadata=ChatMetadata(trace_id=trace_id, session_id=request.session_id, intent="agent_studio", resolved_context=request.context, execution_time_ms=latency_ms),
        )


async def _run_chat_graph(request: ChatRequest) -> ChatResponse:
    trace_id = str(uuid.uuid4())
    started = time.perf_counter()
    # Prior turns from this session, loaded once per request - a plain
    # SQLite table keyed by session_id (see conversation_store.py), not a
    # LangGraph checkpointer. Each graph run is otherwise fully stateless:
    # nodes only read "history", nothing in the graph accumulates it.
    history = conversations.load_history(request.session_id)
    initial = {
        "question": request.question,
        "language": request.language,
        "session_id": request.session_id,
        "history": history,
        "dashboard_state": request.context.model_dump(),
        "trace_id": trace_id,
        "repair_attempts": 0,
        "fallback_used": False,
    }
    try:
        state = await workflow.ainvoke(initial)
        latency_ms = round((time.perf_counter() - started) * 1000)
        answer = ExecutiveAnswer.model_validate(state.get("answer") or {"summary": "No validated answer.", "drivers": [], "recommended_actions": [], "caveats": []})
        raw_chart = state.get("chart_spec")
        chart = ChartSpec.model_validate(raw_chart) if raw_chart and raw_chart.get("type") != "none" else None
        # unit_format is read from raw_chart directly (not from `chart`,
        # which becomes None whenever type == "none" - the common case for
        # a single-value, no-dimension answer) so DataTable still gets it
        # even when there's no chart to render.
        unit_format = raw_chart.get("unit_format") if raw_chart else None
        rows = state.get("rows", [])
        columns = list(rows[0].keys()) if rows else []
        status = state.get("status", "ok")
        resolved_state = DashboardState.model_validate(state.get("resolved_state") or request.context.model_dump())
        conversations.append_turn(request.session_id, request.question, answer.summary)
        telemetry.record(
            trace_id=trace_id,
            question=request.question,
            intent=state.get("intent", "unknown"),
            status=status,
            latency_ms=latency_ms,
            validation_status=state.get("validation_status", "not_applicable"),
            rows_returned=len(rows),
            metadata={
                "fallback": bool(state.get("fallback_used")),
                "ui_actions": len(state.get("ui_actions", [])),
                "model": state.get("model_telemetry") or {},
                "data": state.get("data_telemetry") or {},
            },
        )
        return ChatResponse(
            status=status if status in {"ok", "fallback", "error"} else "ok",
            question=request.question,
            answer=answer,
            data=QueryData(columns=columns, rows=rows, unit_format=unit_format),
            chart_spec=chart,
            ui_actions=[ui_action_adapter.validate_python(a) for a in state.get("ui_actions", [])],
            metadata=ChatMetadata(
                trace_id=trace_id,
                session_id=request.session_id,
                intent=state.get("intent", "unknown"),
                resolved_context=resolved_state,
                execution_time_ms=latency_ms,
            ),
        )
    except Exception:
        logger.exception("Chat workflow failed trace_id=%s", trace_id)
        latency_ms = round((time.perf_counter() - started) * 1000)
        telemetry.record(trace_id=trace_id, question=request.question, intent="error", status="error", latency_ms=latency_ms, metadata={"safe_error": True})
        return ChatResponse(
            status="error",
            question=request.question,
            answer=ExecutiveAnswer(summary="Workflow could not complete safely.", drivers=[], recommended_actions=["Retry the request or contact the application operator with the trace ID."], caveats=["Internal error details are not exposed."]),
            data=QueryData(),
            chart_spec=None,
            ui_actions=[],
            metadata=ChatMetadata(trace_id=trace_id, session_id=request.session_id, intent="error", resolved_context=request.context, execution_time_ms=latency_ms),
        )
