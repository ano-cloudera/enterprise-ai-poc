from __future__ import annotations

from typing import Any, TypedDict


class AskDataState(TypedDict, total=False):
    request_id: str
    session_id: str
    question: str
    original_question: str
    conversation_history: list[dict[str, Any]]
    provider: str
    model: str
    use_local_agent: bool
    semantic_resolution: dict[str, Any]
    governed_partial_caveats: list[str]
    semantic_context: dict[str, Any]
    strategy: str
    query_plan: dict[str, Any]
    sql: str
    validated_sql: str
    validation_error: str
    query_result: dict[str, Any]
    answer: dict[str, Any]
    chart_spec: dict[str, Any] | None
    status: str
    error: str
    retry_count: int
    timings: dict[str, float]
