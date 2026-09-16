from __future__ import annotations

from functools import reduce

from sqlglot import exp

from app.semantic.intent import AnalyticalIntent
from app.semantic.loader import governed_table_name
from app.semantic.models import DatasetDefinition, MetricDefinition, SemanticProject


def _and(expressions: list[exp.Expression]) -> exp.Expression:
    if not expressions:
        raise ValueError("At least one SQL predicate is required")
    return reduce(lambda left, right: exp.and_(left, right), expressions)


def _aggregate(metric: MetricDefinition, value: exp.Expression | None = None) -> exp.Expression:
    expression = value or exp.column(metric.expression)
    if metric.aggregation == "sum":
        return exp.Sum(this=expression)
    if metric.aggregation == "avg":
        return exp.Avg(this=expression)
    if metric.aggregation == "min":
        return exp.Min(this=expression)
    if metric.aggregation == "max":
        return exp.Max(this=expression)
    if metric.aggregation == "count_distinct":
        return exp.Count(this=exp.Distinct(expressions=[expression]))
    return exp.Count(this=expression)


def _date_predicate(column: str, start: str, end: str) -> exp.Expression:
    return exp.and_(
        exp.GTE(this=exp.column(column), expression=exp.cast(exp.Literal.string(start), "DATE")),
        exp.LT(this=exp.column(column), expression=exp.cast(exp.Literal.string(end), "DATE")),
    )


def _dataset_for(intent: AnalyticalIntent, project: SemanticProject) -> DatasetDefinition:
    required_dimensions = {item for item in [*intent.dimensions, *intent.filters] if item != "time"}
    for dataset in project.datasets.values():
        if intent.metric in dataset.metrics and required_dimensions.issubset(dataset.dimensions):
            return dataset
    raise ValueError("No governed dataset satisfies the normalized analytical intent")


def _dimension_expressions(intent: AnalyticalIntent, dataset: DatasetDefinition) -> list[tuple[str, exp.Expression]]:
    result: list[tuple[str, exp.Expression]] = []
    for dimension in intent.dimensions:
        if dimension == "time":
            time_dimension = next(iter(dataset.time_dimensions.values()), None)
            if time_dimension is None or intent.time.grain not in time_dimension.grains:
                raise ValueError("Requested time grain is not governed for the selected dataset")
            if intent.time.grain == "month":
                expression = exp.Substring(
                    this=exp.cast(exp.column(time_dimension.column), "STRING"),
                    start=exp.Literal.number(1),
                    length=exp.Literal.number(7),
                )
            elif intent.time.grain == "day":
                expression = exp.cast(exp.column(time_dimension.column), "DATE")
            else:
                raise ValueError("The requested time grain is not supported by the PoC SQL compiler")
            result.append(("period", expression))
        else:
            result.append((dimension, exp.column(dataset.dimensions[dimension].column)))
    return result


def _filter_predicates(intent: AnalyticalIntent, dataset: DatasetDefinition) -> list[exp.Expression]:
    predicates: list[exp.Expression] = []
    for target, values in intent.filters.items():
        column = dataset.dimensions[target].column
        predicates.append(exp.column(column).isin(*[exp.Literal.string(value) for value in values]))
    return predicates


def _comparison_projections(metric: MetricDefinition, time_column: str, intent: AnalyticalIntent) -> list[exp.Expression]:
    current_condition = _date_predicate(time_column, intent.time.start or "", intent.time.end or "")
    previous_condition = _date_predicate(time_column, intent.comparison.start or "", intent.comparison.end or "")

    def conditional_aggregate(condition: exp.Expression) -> exp.Expression:
        case = exp.Case(ifs=[exp.If(this=condition, true=exp.column(metric.expression))], default=exp.Literal.number(0))
        return _aggregate(metric, case)

    current = conditional_aggregate(current_condition)
    previous = conditional_aggregate(previous_condition)
    change = exp.Sub(this=current.copy(), expression=previous.copy())
    percentage = exp.Case(
        ifs=[exp.If(this=exp.EQ(this=previous.copy(), expression=exp.Literal.number(0)), true=exp.Null())],
        default=exp.Div(
            this=exp.Mul(this=exp.Paren(this=change.copy()), expression=exp.Literal.number(100)),
            expression=previous.copy(),
        ),
    )
    return [
        exp.alias_(current, "current_value"),
        exp.alias_(previous, "previous_value"),
        exp.alias_(change, "absolute_change"),
        exp.alias_(percentage, "percentage_change"),
    ]


def generate_semantic_sql(
    intent: AnalyticalIntent,
    project: SemanticProject,
    dialect: str = "duckdb",
    catalog: str = "",
    schema: str = "",
) -> str:
    """Compile a validated analytical intent to one governed read-only query."""
    dataset = _dataset_for(intent, project)
    metric = dataset.metrics[intent.metric]
    time_dimension = next(iter(dataset.time_dimensions.values()), None)
    if time_dimension is None or not intent.time.start or not intent.time.end:
        raise ValueError("A normalized explicit date range is required")
    dimensions = _dimension_expressions(intent, dataset)
    projections = [exp.alias_(expression.copy(), alias) for alias, expression in dimensions]
    predicates = _filter_predicates(intent, dataset)

    if intent.comparison.type == "previous_period":
        if not intent.comparison.start or not intent.comparison.end:
            raise ValueError("An explicit previous-period range is required")
        projections.extend(_comparison_projections(metric, time_dimension.column, intent))
        predicates.append(_date_predicate(time_dimension.column, intent.comparison.start, intent.time.end))
    else:
        projections.append(exp.alias_(_aggregate(metric), "value"))
        predicates.append(_date_predicate(time_dimension.column, intent.time.start, intent.time.end))

    source = governed_table_name(dataset, dialect, catalog, schema)
    query = exp.select(*projections).from_(exp.to_table(source)).where(_and(predicates))
    if dimensions:
        query = query.group_by(*[expression.copy() for _, expression in dimensions])
    for item in intent.sort:
        query = query.order_by(exp.Ordered(this=exp.column(item.field), desc=item.direction == "desc"), append=True)
    if not intent.sort and dimensions:
        order_field = "period" if intent.pattern == "trend" else ("percentage_change" if intent.comparison.type == "previous_period" else "value")
        query = query.order_by(exp.Ordered(this=exp.column(order_field), desc=intent.pattern != "trend"))
    query = query.limit(intent.limit)
    return query.sql(dialect=dialect)
