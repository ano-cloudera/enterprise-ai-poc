from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class DashboardDateRange(BaseModel):
    preset: str | None = "current_month"
    start: str | None = None
    end: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_preset(cls, value):
        if isinstance(value, str):
            return {"preset": value, "start": None, "end": None}
        return value


class DashboardHighlight(BaseModel):
    target: str
    value: str


class AppliedContext(BaseModel):
    kind: Literal["filter", "date_range"]
    target: str
    label: str


class DashboardState(BaseModel):
    """Shared conversational + dashboard state. Frontend sends the latest applied state back on follow-up."""

    filters: dict[str, list[str]] = Field(default_factory=dict)
    date_range: DashboardDateRange = Field(default_factory=DashboardDateRange)
    metric: str = "net_sales"
    dimension: str = "region"
    highlights: list[DashboardHighlight] = Field(default_factory=list)
    ai_applied_context: list[AppliedContext] = Field(default_factory=list)
    revision: int = 0


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str = "demo-session"
    language: Literal["id", "en", "auto"] = "auto"
    history: list[ChatMessage] = Field(default_factory=list)
    context: DashboardState = Field(
        default_factory=DashboardState,
        validation_alias=AliasChoices("context", "dashboard_state"),
    )


class DashboardRequest(BaseModel):
    context: DashboardState = Field(default_factory=DashboardState)


class ChartSeries(BaseModel):
    name: str
    data: list[float | int | str | None]


class ChartSpec(StrictModel):
    type: Literal["line", "bar", "area", "pie", "table", "none"] = "none"
    title: str = ""
    x: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    x_label: str | None = None
    y_label: str | None = None
    dimension: str | None = None
    metric: str | None = None
    target: Literal["chat", "dashboard", "both"] = "chat"


class ExecutiveAnswer(StrictModel):
    summary: str
    drivers: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


UIActionType = Literal[
    "SET_FILTER",
    "SET_DATE_RANGE",
    "CHANGE_METRIC",
    "CHANGE_DIMENSION",
    "RENDER_CHART",
    "SHOW_TABLE",
    "HIGHLIGHT_CARD",
    "RESET_FILTER",
]

ActionTarget = Annotated[str, StringConstraints(min_length=1, max_length=100, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")]
ActionValue = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class DateRangeValue(StrictModel):
    start: str
    end: str


class RenderChartValue(StrictModel):
    chart_type: Literal["line", "bar", "area", "pie", "table"]
    dimension: ActionTarget
    metric: ActionTarget


class ShowTableValue(StrictModel):
    columns: list[ActionTarget] = Field(default_factory=list)


class SetFilterAction(StrictModel):
    type: Literal["SET_FILTER"]
    target: ActionTarget
    value: list[ActionValue] = Field(min_length=1)


class SetDateRangeAction(StrictModel):
    type: Literal["SET_DATE_RANGE"]
    value: ActionValue | DateRangeValue


class ChangeMetricAction(StrictModel):
    type: Literal["CHANGE_METRIC"]
    value: ActionTarget


class ChangeDimensionAction(StrictModel):
    type: Literal["CHANGE_DIMENSION"]
    value: ActionTarget


class RenderChartAction(StrictModel):
    type: Literal["RENDER_CHART"]
    target: Literal["chat", "dashboard", "both"]
    value: RenderChartValue


class ShowTableAction(StrictModel):
    type: Literal["SHOW_TABLE"]
    target: Literal["chat", "dashboard", "both"]
    value: ShowTableValue = Field(default_factory=ShowTableValue)


class HighlightCardAction(StrictModel):
    type: Literal["HIGHLIGHT_CARD"]
    target: ActionTarget
    value: ActionValue | list[ActionValue]


class ResetFilterAction(StrictModel):
    type: Literal["RESET_FILTER"]
    target: ActionTarget | None = None


UIAction = Annotated[
    Union[
        SetFilterAction,
        SetDateRangeAction,
        ChangeMetricAction,
        ChangeDimensionAction,
        RenderChartAction,
        ShowTableAction,
        HighlightCardAction,
        ResetFilterAction,
    ],
    Field(discriminator="type"),
]
ui_action_adapter = TypeAdapter(UIAction)


class QueryData(StrictModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ChatMetadata(StrictModel):
    trace_id: str
    session_id: str
    intent: str
    resolved_context: DashboardState = Field(default_factory=DashboardState)
    execution_time_ms: int = 0


class ChatResponse(StrictModel):
    status: Literal["ok", "fallback", "error"]
    question: str
    answer: ExecutiveAnswer
    data: QueryData = Field(default_factory=QueryData)
    chart_spec: ChartSpec | None = None
    ui_actions: list[UIAction] = Field(default_factory=list)
    metadata: ChatMetadata


class BackendHealth(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    status: Literal["ok", "unknown", "unavailable", "auth_required", "auth_failed", "misconfigured", "degraded"]
    name: str
    type: str
    catalog: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")

    @property
    def schema(self) -> str | None:
        return self.schema_name


class ModelBackendHealth(BaseModel):
    mode: Literal["mock", "remote"]
    status: Literal["mock", "ok", "unavailable", "auth_required", "unknown"]
    provider: str
    model: str


class HealthResponse(BaseModel):
    status: str
    app: str
    project: str
    data_backend: BackendHealth
    model_backend: ModelBackendHealth
    timestamp: datetime


class PublicConfigResponse(BaseModel):
    project_id: str
    project_name: str
    project_subtitle: str
    brand: dict[str, str]
    model_name: str
    data_backend: str
    guardrails_enabled: bool


class SettingsPatch(BaseModel):
    language: Literal["id", "en", "auto"] | None = None
    system_prompt: str | None = None
    model_name: str | None = None


class DashboardOverview(BaseModel):
    period: str
    kpis: list[dict[str, Any]]
    sales_trend: list[dict[str, Any]]
    region_sales: list[dict[str, Any]]
    top_products: list[dict[str, Any]]
    channel_share: list[dict[str, Any]]
    ai_insight: dict[str, Any]


class MonitoringSummary(BaseModel):
    total_queries: int
    avg_response_time_ms: int
    success_rate: float
    validation_reject_rate: float
    usage_trend: list[dict[str, Any]]
    recent_activity: list[dict[str, Any]]
