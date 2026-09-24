from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    question: str
    language: str
    session_id: str
    # Prior turns in this session, oldest first - loaded from
    # ConversationStore (app/services/conversation_store.py) by
    # services/chat.py before each graph invocation. Nodes only ever read
    # this field; it never accumulates within the graph itself (no
    # LangGraph checkpointer is used - see workflow.py).
    history: list[dict[str, str]]
    trace_id: str
    dashboard_state: dict[str, Any]
    resolved_state: dict[str, Any]
    intent: str
    semantic_context: str
    semantic_resolution: dict[str, Any]
    semantic_plan: dict[str, Any]
    capability_status: str
    scope_notice: str
    analytical_intent: dict[str, Any]
    forecast_intent: dict[str, Any]
    weather_intent: dict[str, Any]
    weather_evidence: dict[str, Any]
    market_intent: dict[str, Any]
    market_evidence: dict[str, Any]
    sql: str
    sql_reason: str
    validated_sql: str
    validation_status: str
    validation_error: str
    repair_attempts: int
    rows: list[dict[str, Any]]
    result_check_status: str
    result_check_error: str
    answer: dict[str, Any]
    chart_spec: dict[str, Any]
    ui_actions: list[dict[str, Any]]
    status: str
    fallback_used: bool
    model_telemetry: dict[str, Any]
    data_telemetry: dict[str, Any]
    guardrail_error: str
    reset_requested: bool
    governance_probe_detected: bool
