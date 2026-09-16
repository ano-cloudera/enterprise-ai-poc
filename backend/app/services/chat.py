from __future__ import annotations

import time
import uuid
import logging

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


telemetry = TelemetryStore()
logger = logging.getLogger(__name__)


async def run_chat(request: ChatRequest) -> ChatResponse:
    trace_id = str(uuid.uuid4())
    started = time.perf_counter()
    initial = {
        "question": request.question,
        "language": request.language,
        "session_id": request.session_id,
        "history": [item.model_dump() for item in request.history[-8:]],
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
        rows = state.get("rows", [])
        columns = list(rows[0].keys()) if rows else []
        status = state.get("status", "ok")
        resolved_state = DashboardState.model_validate(state.get("resolved_state") or request.context.model_dump())
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
            data=QueryData(columns=columns, rows=rows),
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
