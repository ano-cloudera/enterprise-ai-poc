from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    callable: Callable[..., Any] | None = None
    llm_visible: bool = True


TOOL_REGISTRY = {
    "query_business_data": ToolSpec(
        name="query_business_data",
        description="Read governed business metrics from allowlisted datasets. Read-only.",
    ),
    "forecast_metric": ToolSpec(
        name="forecast_metric",
        description="Forecast a governed metric for a selected dimension and horizon.",
    ),
    "lookup_external_signal": ToolSpec(
        name="lookup_external_signal",
        description="Read configured external signals such as weather or competitor activity.",
    ),
}

# Security-critical functions such as SQL validation are intentionally NOT exposed as optional LLM tools.
