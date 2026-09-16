from __future__ import annotations

from app.core.schemas import (
    ChangeDimensionAction,
    ChangeMetricAction,
    HighlightCardAction,
    RenderChartAction,
    ResetFilterAction,
    SetDateRangeAction,
    SetFilterAction,
    UIAction,
)
from app.semantic.models import SemanticProject


def validate_action_targets(actions: list[UIAction], project: SemanticProject) -> None:
    dimensions = {key for dataset in project.datasets.values() for key in dataset.dimensions}
    metrics = {key for dataset in project.datasets.values() for key in dataset.metrics}
    periods = set(project.resolution.periods)
    for action in actions:
        if isinstance(action, SetFilterAction) and action.target not in dimensions:
            raise ValueError(f"Unknown filter target: {action.target}")
        if isinstance(action, HighlightCardAction) and action.target not in dimensions | metrics:
            raise ValueError(f"Unknown highlight target: {action.target}")
        if isinstance(action, ChangeMetricAction) and action.value not in metrics:
            raise ValueError(f"Unknown metric target: {action.value}")
        if isinstance(action, ChangeDimensionAction) and action.value not in dimensions:
            raise ValueError(f"Unknown dimension target: {action.value}")
        if isinstance(action, RenderChartAction):
            if action.value.dimension not in dimensions and action.value.dimension != "month":
                raise ValueError(f"Unknown chart dimension: {action.value.dimension}")
            if action.value.metric not in metrics:
                raise ValueError(f"Unknown chart metric: {action.value.metric}")
        if isinstance(action, SetDateRangeAction) and isinstance(action.value, str) and action.value not in periods:
            raise ValueError(f"Unknown date range: {action.value}")
        if isinstance(action, ResetFilterAction) and action.target and action.target not in dimensions:
            raise ValueError(f"Unknown reset target: {action.target}")
