from __future__ import annotations

import re
from typing import Any

from app.semantic.intent import AnalyticalIntent
from app.semantic.models import SemanticProject


def _contains(text: str, alias: str) -> bool:
    return bool(alias) and re.search(rf"(?<!\w){re.escape(alias.casefold())}(?!\w)", text) is not None


def _first_matching_key(text: str, configured: dict[str, list[str]]) -> str | None:
    for key, aliases in configured.items():
        if any(_contains(text, alias) for alias in [key, *aliases]):
            return key
    return None


def resolve_analytical_intent(question: str, context: dict[str, Any], project: SemanticProject) -> dict[str, Any]:
    """Resolve only configured semantic vocabulary into a small analytical intent candidate."""
    text = question.casefold()
    resolution = project.resolution
    filters = {key: list(values) for key, values in (context.get("filters") or {}).items() if values}
    explicit_dimensions: list[str] = []

    matched_entities: dict[str, list[str]] = {}
    for target, configured_values in resolution.entities.items():
        values = [item.value for item in configured_values if any(_contains(text, alias) for alias in [item.value, *item.aliases])]
        if values:
            matched_entities[target] = list(dict.fromkeys(values))
    filters.update(matched_entities)

    metric = context.get("metric") or resolution.default_metric
    metric_explicitly_matched = False
    for dataset in project.datasets.values():
        for key, definition in dataset.metrics.items():
            if any(_contains(text, alias) for alias in [key, definition.label, *definition.aliases]):
                metric = key
                metric_explicitly_matched = True

    # The question asked for a specific count/amount ("jumlah", "berapa
    # banyak", "how many") but named nothing that maps to a configured
    # metric - e.g. "berapa jumlah customer" when there is no customer-count
    # metric, only a customer_segment dimension. Falling back to
    # default_metric here would silently answer a different question
    # ("Net Sales") as if it were the one asked - flag it instead so the
    # caller can say the data isn't available rather than substituting it.
    asked_for_a_measure = any(_contains(text, term) for term in resolution.measure_request_terms)
    metric_unavailable = asked_for_a_measure and not metric_explicitly_matched

    for dataset in project.datasets.values():
        for key, definition in dataset.dimensions.items():
            if any(_contains(text, alias) for alias in [key, definition.label, *definition.aliases]):
                if key not in explicit_dimensions:
                    explicit_dimensions.append(key)

    period = _first_matching_key(text, resolution.periods)
    if period is None:
        date_range = context.get("date_range") or {}
        period = date_range if isinstance(date_range, str) else date_range.get("preset")
    period = period or "current_month"
    grain = _first_matching_key(text, resolution.grains) or "month"

    pattern = _first_matching_key(text, {key: value.aliases for key, value in resolution.patterns.items()}) or "kpi"
    if any(len(values) > 1 for values in matched_entities.values()):
        pattern = "entity_comparison"
    pattern_definition = resolution.patterns.get(pattern)
    dimensions = explicit_dimensions or (list(pattern_definition.dimensions) if pattern_definition else [])

    comparison_type = pattern_definition.comparison if pattern_definition else "none"
    explicit_comparison = _first_matching_key(text, resolution.comparisons)
    if explicit_comparison:
        comparison_type = explicit_comparison
    if pattern == "entity_comparison":
        comparison_type = "entity"

    sort: list[dict[str, str]] = []
    if pattern_definition and pattern_definition.sort_field:
        direction = pattern_definition.sort_direction
        if any(_contains(text, alias) for alias in resolution.positive_sort_aliases):
            direction = "desc"
        sort.append({"field": pattern_definition.sort_field, "direction": direction})

    limit = 50
    if pattern_definition:
        for alias in pattern_definition.aliases:
            match = re.search(rf"(?<!\w){re.escape(alias.casefold())}\s+(\d+)(?!\w)", text)
            if match:
                limit = int(match.group(1))
                break

    return {
        "intent_type": "analysis",
        "pattern": pattern,
        "metric": metric,
        "dimensions": dimensions,
        "filters": filters,
        "time": {"period": period, "grain": grain},
        "comparison": {"type": comparison_type},
        "sort": sort,
        "limit": limit,
        # Not part of AnalyticalIntent (the governed intent schema passed to
        # SQL generation) - a signal consumed only by graph/nodes.py's
        # resolve_semantics to short-circuit to a "data not available"
        # answer instead of silently querying a substitute metric. Pop it
        # before normalize_analytical_intent validates the rest as
        # AnalyticalIntent.
        "metric_unavailable": metric_unavailable,
    }


def normalize_analytical_intent(candidate: dict[str, Any], project: SemanticProject) -> AnalyticalIntent:
    """Validate canonical names and expand configured time/comparison presets to explicit ranges."""
    intent = AnalyticalIntent.model_validate(candidate)
    datasets = list(project.datasets.values())
    metrics = {key for dataset in datasets for key in dataset.metrics}
    dimensions = {key for dataset in datasets for key in dataset.dimensions}
    if intent.metric not in metrics:
        raise ValueError(f"Unknown semantic metric: {intent.metric}")
    if any(dimension != "time" and dimension not in dimensions for dimension in intent.dimensions):
        raise ValueError("Unknown semantic dimension")
    configured_entities = {target: {item.value for item in values} for target, values in project.resolution.entities.items()}
    for target, values in intent.filters.items():
        if target not in dimensions or target not in configured_entities:
            raise ValueError(f"Unknown governed filter: {target}")
        if any(value not in configured_entities[target] for value in values):
            raise ValueError(f"Unknown governed filter value: {target}")

    period = project.resolution.period_ranges.get(intent.time.period)
    if period is None:
        raise ValueError(f"Unknown configured period: {intent.time.period}")
    intent.time.start = period.start
    intent.time.end = period.end
    if intent.comparison.type == "previous_period":
        comparison_period = project.resolution.comparison_periods.get(intent.time.period)
        comparison = project.resolution.period_ranges.get(comparison_period or "")
        if comparison is None:
            raise ValueError(f"No comparison period configured for: {intent.time.period}")
        intent.comparison.period = comparison_period
        intent.comparison.start = comparison.start
        intent.comparison.end = comparison.end
    maximum = min(dataset.query_rules.max_limit for dataset in datasets if intent.metric in dataset.metrics)
    intent.limit = min(intent.limit, maximum, 500)
    return intent
