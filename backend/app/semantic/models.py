from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class MetricDefinition(BaseModel):
    label: str
    expression: str
    aggregation: Literal["sum", "avg", "count", "count_distinct", "min", "max"]
    type: str = "number"
    aliases: list[str] = Field(default_factory=list)
    description: str = ""


class DimensionDefinition(BaseModel):
    label: str
    column: str
    type: str = "categorical"
    aliases: list[str] = Field(default_factory=list)
    description: str = ""


class TimeDimensionDefinition(BaseModel):
    label: str
    column: str
    grains: list[str] = Field(default_factory=lambda: ["day", "month"])


class RelationshipDefinition(BaseModel):
    dataset: str
    type: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"] = "many_to_one"
    join: list[str] = Field(default_factory=list)
    description: str = ""


class QueryRules(BaseModel):
    allowed_fields: list[str] = Field(default_factory=list)
    default_limit: int = 200
    max_limit: int = 5000
    require_date_filter: bool = False
    allowed_functions: list[str] = Field(default_factory=lambda: ["date_format", "strftime"])
    notes: list[str] = Field(default_factory=list)


class TrinoTableDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    table: str
    catalog: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")

    @property
    def schema(self) -> str | None:
        return self.schema_name


class DatasetDefinition(BaseModel):
    name: str
    source: str
    trino: TrinoTableDefinition | None = None
    description: str = ""
    primary_key: list[str] = Field(default_factory=list)
    metrics: dict[str, MetricDefinition] = Field(default_factory=dict)
    dimensions: dict[str, DimensionDefinition] = Field(default_factory=dict)
    time_dimensions: dict[str, TimeDimensionDefinition] = Field(default_factory=dict)
    relationships: dict[str, RelationshipDefinition] = Field(default_factory=dict)
    query_rules: QueryRules = Field(default_factory=QueryRules)


class EntityValueDefinition(BaseModel):
    value: str
    aliases: list[str] = Field(default_factory=list)


class PeriodRangeDefinition(BaseModel):
    start: str
    end: str


class PatternDefinition(BaseModel):
    aliases: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    comparison: Literal["none", "previous_period", "entity"] = "none"
    sort_field: str | None = None
    sort_direction: Literal["asc", "desc"] = "desc"


class ResolutionDefinition(BaseModel):
    default_metric: str | None = None
    default_dimension: str | None = None
    entities: dict[str, list[EntityValueDefinition]] = Field(default_factory=dict)
    periods: dict[str, list[str]] = Field(default_factory=dict)
    period_ranges: dict[str, PeriodRangeDefinition] = Field(default_factory=dict)
    reset_phrases: list[str] = Field(default_factory=list)
    comparison_periods: dict[str, str] = Field(default_factory=dict)
    comparisons: dict[str, list[str]] = Field(default_factory=dict)
    grains: dict[str, list[str]] = Field(default_factory=dict)
    patterns: dict[str, PatternDefinition] = Field(default_factory=dict)
    positive_sort_aliases: list[str] = Field(default_factory=list)


class GoldenExpected(BaseModel):
    metric: str
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, list[str]] = Field(default_factory=dict)
    period: str
    comparison: Literal["none", "previous_period", "entity"]
    pattern: str


class GoldenQuestion(BaseModel):
    id: str
    question: str
    context: dict[str, Any] = Field(default_factory=dict)
    expected: GoldenExpected
    generates_sql: bool = True


class ForecastGoldenQuestion(BaseModel):
    id: str
    question: str
    context: dict[str, Any] = Field(default_factory=dict)
    dimension_type: Literal["total", "region", "product", "channel"]
    dimension_value: str | None = None
    forecast_period: str
    expected_status: Literal["ok", "FORECAST_NOT_AVAILABLE"] = "ok"


class SemanticProject(BaseModel):
    project: str
    datasets: dict[str, DatasetDefinition]
    business_terms: dict[str, str] = Field(default_factory=dict)
    allowed_questions: list[str] = Field(default_factory=list)
    business_definitions: dict[str, Any] = Field(default_factory=dict)
    resolution: ResolutionDefinition = Field(default_factory=ResolutionDefinition)
    golden_questions: list[GoldenQuestion] = Field(default_factory=list)
    forecast_golden_questions: list[ForecastGoldenQuestion] = Field(default_factory=list)
