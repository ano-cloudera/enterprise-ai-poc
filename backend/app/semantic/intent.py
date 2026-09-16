from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AnalyticalTime(BaseModel):
    period: str
    grain: str = "month"
    start: str | None = None
    end: str | None = None


class AnalyticalComparison(BaseModel):
    type: Literal["none", "previous_period", "entity"] = "none"
    period: str | None = None
    start: str | None = None
    end: str | None = None


class AnalyticalSort(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "desc"


class AnalyticalIntent(BaseModel):
    intent_type: Literal["analysis"] = "analysis"
    pattern: Literal["kpi", "trend", "breakdown", "top_bottom", "period_comparison", "entity_comparison"]
    metric: str
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, list[str]] = Field(default_factory=dict)
    time: AnalyticalTime
    comparison: AnalyticalComparison = Field(default_factory=AnalyticalComparison)
    sort: list[AnalyticalSort] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=500)
