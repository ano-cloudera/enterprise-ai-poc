from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    question: str
    language: str
    session_id: str
    history: list[dict[str, str]]
    trace_id: str
    dashboard_state: dict[str, Any]
    resolved_state: dict[str, Any]
    intent: str
    semantic_context: str
    semantic_resolution: dict[str, Any]
    analytical_intent: dict[str, Any]
    forecast_intent: dict[str, Any]
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
