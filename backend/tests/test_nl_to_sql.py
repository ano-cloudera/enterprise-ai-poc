from __future__ import annotations

import inspect

import pytest

from app.core.schemas import DashboardState
from app.graph import nodes
from app.graph.nodes import analyze_result, repair_sql, result_checker, ui_action_generator, validate_sql, visualization_planner
from app.graph.workflow import _after_validation
from app.semantic.loader import load_semantic_project
from app.semantic.resolver import normalize_analytical_intent, resolve_analytical_intent
from app.tools.semantic_sql import generate_semantic_sql
from app.tools.sql_validator import validate_readonly_sql
from app.services.query import QueryContext, query_service


PROJECT = load_semantic_project("tempo_scan")


def resolve(question: str, context: DashboardState | None = None):
    candidate = resolve_analytical_intent(question, (context or DashboardState()).model_dump(), PROJECT)
    return normalize_analytical_intent(candidate, PROJECT)


def test_metric_and_project_aliases_resolve_canonically():
    intent = resolve("Berapa sales Jabar untuk MT bulan ini?")
    assert intent.metric == "net_sales"
    assert intent.filters["region"] == ["Jawa Barat"]
    assert intent.filters["channel"] == ["Modern Trade"]


def test_current_month_and_previous_period_are_explicit():
    intent = resolve("Kenapa sales Jawa Barat turun bulan ini?")
    assert intent.time.period == "current_month"
    assert (intent.time.start, intent.time.end) == ("2024-03-01", "2024-04-01")
    assert intent.comparison.type == "previous_period"
    assert intent.comparison.period == "previous_month"
    assert (intent.comparison.start, intent.comparison.end) == ("2024-02-01", "2024-03-01")


def test_follow_up_preserves_filters_and_explicit_region_overrides():
    context = DashboardState(filters={"region": ["Jawa Barat"], "channel": ["Modern Trade"]})
    inherited = resolve("Produk mana yang paling turun?", context)
    assert inherited.filters == {"region": ["Jawa Barat"], "channel": ["Modern Trade"]}
    overridden = resolve("Kalau Jawa Timur?", context)
    assert overridden.filters["region"] == ["Jawa Timur"]
    assert overridden.filters["channel"] == ["Modern Trade"]


def test_breakdown_top_bottom_and_trend_patterns():
    product = resolve("Produk mana yang paling turun?")
    assert product.pattern == "top_bottom"
    assert product.dimensions == ["product"]
    assert product.comparison.type == "previous_period"
    assert product.sort[0].field == "percentage_change"
    assert product.sort[0].direction == "asc"

    trend = resolve("Tampilkan tren sales 3 bulan terakhir.")
    assert trend.pattern == "trend"
    assert trend.dimensions == ["time"]
    assert trend.time.period == "last_3_months"
    assert trend.time.grain == "month"
    assert (trend.time.start, trend.time.end) == ("2024-01-01", "2024-04-01")


def test_region_decline_word_order_selects_the_largest_negative_change():
    intent = resolve("Region mana yang turun paling besar?")
    assert intent.pattern == "top_bottom"
    assert intent.dimensions == ["region"]
    assert intent.sort[0].field == "percentage_change"
    assert intent.sort[0].direction == "asc"

    result = query_service.execute_validated(
        generate_semantic_sql(intent, PROJECT),
        QueryContext(purpose="test.region_decline_word_order", project_id="tempo_scan"),
    )
    assert result.rows[0]["region"] == "Jawa Barat"
    assert result.rows[0]["percentage_change"] == pytest.approx(-16.620605, abs=0.001)


def test_top_n_normalizes_limit_and_sort_direction():
    intent = resolve("Top 3 produk tumbuh")
    assert intent.pattern == "top_bottom"
    assert intent.limit == 3
    assert intent.dimensions == ["product"]
    assert intent.sort[0].direction == "desc"


def test_entity_comparison_accumulates_both_values():
    intent = resolve("Bandingkan Jawa Barat dengan Jawa Timur.")
    assert intent.pattern == "entity_comparison"
    assert intent.dimensions == ["region"]
    assert intent.filters["region"] == ["Jawa Barat", "Jawa Timur"]
    assert intent.comparison.type == "entity"


@pytest.mark.parametrize(
    ("question", "sql_fragments"),
    [
        ("Berapa sales Jawa Barat bulan ini?", ["sales_amount", "sales_date", "Jawa Barat"]),
        ("Kalau cuma Modern Trade?", ["channel_name", "Modern Trade"]),
        ("Produk mana yang paling turun?", ["product_name", "current_value", "previous_value", "percentage_change"]),
        ("Tampilkan tren sales 3 bulan terakhir.", ["sales_date", "2024-01-01", "2024-04-01"]),
    ],
)
def test_semantic_sql_contains_only_governed_structure(question, sql_fragments):
    context = DashboardState(filters={"region": ["Jawa Barat"]}) if question.startswith("Kalau") else None
    intent = resolve(question, context)
    sql = generate_semantic_sql(intent, PROJECT)
    assert all(fragment.lower() in sql.lower() for fragment in sql_fragments)
    validation = validate_readonly_sql(sql, PROJECT)
    assert validation.valid, validation.error
    assert "commercial_sales_daily" in sql.lower()
    assert "drop " not in sql.lower()


def test_comparison_sql_applies_prior_period_and_both_active_filters():
    context = DashboardState(filters={"region": ["Jawa Barat"], "channel": ["Modern Trade"]})
    intent = resolve("Produk mana yang paling turun?", context)
    sql = generate_semantic_sql(intent, PROJECT)
    assert "2024-02-01" in sql and "2024-03-01" in sql and "2024-04-01" in sql
    assert "Jawa Barat" in sql and "Modern Trade" in sql


def test_comparison_percentage_uses_change_over_previous_value():
    intent = resolve("Produk mana yang paling turun?")
    result = query_service.execute_validated(
        generate_semantic_sql(intent, PROJECT),
        QueryContext(purpose="test.semantic_comparison", project_id="tempo_scan"),
    )
    row = result.rows[0]
    expected = (row["current_value"] - row["previous_value"]) / row["previous_value"] * 100
    assert row["percentage_change"] == pytest.approx(expected)


def test_validation_route_allows_exactly_one_repair_attempt():
    assert _after_validation({"validation_status": "rejected", "repair_attempts": 0}) == "repair_sql"
    assert _after_validation({"validation_status": "rejected", "repair_attempts": 1}) == "fallback"


def test_result_checker_controlled_outcomes():
    intent = resolve("Produk mana yang paling turun?").model_dump()
    assert result_checker({"rows": [], "analytical_intent": intent})["result_check_status"] == "EMPTY"
    rows = [{"product": "A", "current_value": 10, "previous_value": 0, "absolute_change": 10, "percentage_change": None}]
    assert result_checker({"rows": rows, "analytical_intent": intent})["result_check_status"] == "INSUFFICIENT_DATA"
    assert result_checker({"rows": [{"unexpected": 1}], "analytical_intent": intent})["result_check_status"] == "INVALID_RESULT"
    null_rows = [{"product": "A", "current_value": None, "previous_value": None, "absolute_change": None, "percentage_change": None}]
    assert result_checker({"rows": null_rows, "analytical_intent": intent})["result_check_status"] == "INVALID_RESULT"
    valid_row = {"product": "A", "current_value": 1, "previous_value": 1, "absolute_change": 0, "percentage_change": 0}
    assert result_checker({"rows": [valid_row] * 5001, "analytical_intent": intent})["result_check_status"] == "INVALID_RESULT"


@pytest.mark.asyncio
async def test_invalid_repair_is_attempted_once_then_routes_to_fallback(monkeypatch):
    monkeypatch.setattr(nodes, "generate_semantic_sql", lambda *_: "DROP TABLE commercial_sales_daily")
    repaired = await repair_sql({"sql": "not sql", "analytical_intent": resolve("Berapa sales bulan ini?").model_dump(), "repair_attempts": 0})
    assert repaired["repair_attempts"] == 1
    rejected = validate_sql(repaired)
    assert rejected["validation_status"] == "rejected"
    assert _after_validation(rejected) == "fallback"


@pytest.mark.asyncio
async def test_mock_analysis_is_grounded_only_in_returned_fields():
    intent = resolve("Produk mana yang paling turun?").model_dump()
    rows = [{"product": "Tempra", "current_value": 80.0, "previous_value": 100.0, "absolute_change": -20.0, "percentage_change": -20.0}]
    state = await analyze_result({"rows": rows, "analytical_intent": intent, "question": "Produk mana yang paling turun?"})
    rendered = str(state["answer"])
    assert "Tempra" in rendered and "-20" in rendered
    assert "stockout" not in rendered.lower()
    assert "channel" not in rendered.lower()


def test_chart_planner_uses_intent_and_result_schema():
    trend = resolve("Tampilkan tren sales 3 bulan terakhir.").model_dump()
    trend_state = visualization_planner({"rows": [{"period": "2024-01", "value": 10}], "analytical_intent": trend})
    assert trend_state["chart_spec"]["type"] == "line"
    breakdown = resolve("Sales Jawa Barat berdasarkan produk.").model_dump()
    breakdown_state = visualization_planner({"rows": [{"product": "Tempra", "value": 10}], "analytical_intent": breakdown})
    assert breakdown_state["chart_spec"]["type"] == "bar"


def test_ui_actions_are_derived_from_normalized_intent():
    intent = resolve("Sales Jabar berdasarkan produk bulan ini.").model_dump()
    state = ui_action_generator({
        "analytical_intent": intent,
        "chart_spec": {"type": "bar", "title": "Sales by Product", "x": ["Tempra"], "series": [{"name": "Net Sales", "data": [10]}]},
        "rows": [{"product": "Tempra", "value": 10}],
    })
    action_types = [action["type"] for action in state["ui_actions"]]
    assert action_types[:4] == ["SET_FILTER", "SET_DATE_RANGE", "CHANGE_METRIC", "CHANGE_DIMENSION"]
    assert "RENDER_CHART" in action_types and "SHOW_TABLE" in action_types


def test_generic_resolver_has_no_tempo_business_vocabulary():
    from app.semantic import resolver

    source = inspect.getsource(resolver).lower()
    for forbidden in ("jawa barat", "jawa timur", "modern trade", "jabar", "bulan ini"):
        assert forbidden not in source
