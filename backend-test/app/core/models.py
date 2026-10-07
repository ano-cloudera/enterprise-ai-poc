from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
Strategy = Literal[
    "exploratory_local",
    "conversational",
    "unsupported",
    "clarification",
    "error",
]
ChartType = Literal["bar", "line", "area", "scatter", "pie", "table", "kpi"]


class ChartSpec(StrictModel):
    type: ChartType
    title: str
    x: str | None = None
    y: str | None = None
    series: str | None = None


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
    use_local_agent: bool = False


class QueryData(StrictModel):
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    execution_ms: float = 0


class Timings(StrictModel):
    agent_ms: float = 0
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
    agent_steps: list[dict[str, Any]] = Field(default_factory=list)


class AgentToolCall(StrictModel):
    reasoning: str
    tool: Literal["list_tables", "describe_table", "run_sql", "finish"]  # finish = stop exploring
    table: str | None = None
    sql: str | None = None


class AgentFinishAnswer(StrictModel):
    """Flat finish payload — nested ChartSpec breaks Gemini response_json_schema."""

    direct_answer: str
    executive_summary: str
    insights: list[str] = []
    business_implications: list[str] = []
    caveats: list[str] = []
    data_reference: str


class AgentFinish(StrictModel):
    reasoning: str
    tool: Literal["finish"]
    answer: AgentFinishAnswer
