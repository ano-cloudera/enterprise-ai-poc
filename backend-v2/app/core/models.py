from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelInfo(StrictModel):
    provider: Literal["qwen", "gemini", "openai"]
    id: str
    label: str
    available: bool
    reason: str | None = None


class ModelList(StrictModel):
    models: list[ModelInfo]


Status = Literal["SUCCESS", "CLARIFICATION", "NO_DATA", "UNSUPPORTED", "ERROR"]
Strategy = Literal["governed", "sql_fallback", "clarification", "unsupported"]
ChartType = Literal["bar", "line", "area", "scatter", "pie", "table", "kpi"]


class ChartSpec(StrictModel):
    type: ChartType
    title: str
    x: str | None = None
    y: str | None = None
    series: str | None = None


class QueryPlan(StrictModel):
    strategy: Strategy
    domains: list[str] = []
    metrics: list[str] = []
    dimensions: list[str] = []
    filters: dict[str, Any] = {}
    analysis_type: str = "metric"
    sql: str | None = None
    clarification_question: str | None = None


class AnalysisOutput(StrictModel):
    direct_answer: str
    executive_summary: str
    insights: list[str]
    business_implications: list[str]
    caveats: list[str]
    data_reference: str
    chart_spec: ChartSpec | None = None


class AskDataRequest(StrictModel):
    session_id: str
    question: str
    provider: Literal["qwen", "gemini", "openai"]
    model: str


class QueryData(StrictModel):
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    execution_ms: float = 0


class Timings(StrictModel):
    context_ms: float = 0
    planning_ms: float = 0
    validation_ms: float = 0
    query_ms: float = 0
    analysis_ms: float = 0
    total_ms: float = 0


class AskDataResponse(StrictModel):
    request_id: str
    session_id: str
    status: Status
    provider: str
    model: str
    strategy: Strategy
    answer: AnalysisOutput
    data: QueryData
    chart_spec: ChartSpec | None
    timings: Timings
    retry_count: int = 0
