from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.forecasting.data import load_monthly_sales
from app.forecasting.data import supported_series
from app.forecasting.evaluation import calculate_metrics, select_model
from app.forecasting.features import build_training_features
from app.forecasting.models import MonthlySales
from app.forecasting.models import ForecastLookupResult, ForecastRow
from app.forecasting.inference import generate_forecasts
from app.forecasting.persistence import LocalForecastWriter, TrinoForecastWriter, ForecastWriteSafetyError
from app.forecasting.repository import ForecastRepository
from app.forecasting.tool import ForecastTool, resolve_forecast_intent
from app.graph.nodes import route_intent
from app.graph import nodes
from app.semantic.loader import load_semantic_project
from app.forecasting.training import chronological_split, train_forecast_model
from app.services.query import QueryResult


def test_forecast_history_has_24_chronological_months():
    rows = load_monthly_sales()
    months = sorted({row.month for row in rows})
    assert len(months) == 24
    assert months[0] == date(2022, 4, 1)
    assert months[-1] == date(2024, 3, 1)


def test_extended_history_preserves_existing_hero_totals():
    rows = load_monthly_sales()
    current = sum(row.sales_amount for row in rows if row.month == date(2024, 3, 1) and row.region_name == "Jawa Barat")
    previous = sum(row.sales_amount for row in rows if row.month == date(2024, 2, 1) and row.region_name == "Jawa Barat")
    assert current == pytest.approx(75521.278, abs=0.001)
    assert previous == pytest.approx(90575.469, abs=0.001)


def sample_series():
    return [
        MonthlySales(month=date(2023, month, 1), dimension_type="total", dimension_value="ALL", sales_amount=float(month * 10))
        for month in range(1, 7)
    ]


def test_lag_features_use_previous_periods_only():
    features = build_training_features(sample_series())
    april = features[0]
    assert april.target == 40
    assert (april.lag_1, april.lag_2, april.lag_3) == (30, 20, 10)


def test_rolling_features_exclude_current_and_future_values():
    april = build_training_features(sample_series())[0]
    assert april.rolling_mean_3 == pytest.approx(20)
    assert april.rolling_std_3 == pytest.approx(10)


def test_feature_generation_is_deterministic():
    assert build_training_features(sample_series()) == build_training_features(sample_series())


def test_feature_month_is_the_target_month_not_a_future_source():
    features = build_training_features(sample_series())
    assert features[0].month == date(2023, 4, 1)
    assert features[-1].month == date(2023, 6, 1)


def test_evaluation_metrics_are_correct_and_zero_safe():
    metrics = calculate_metrics([0.0, 2.0, 4.0], [1.0, 2.0, 2.0])
    assert metrics.mae == pytest.approx(1.0)
    assert metrics.rmse == pytest.approx((5 / 3) ** 0.5)
    assert metrics.mape == pytest.approx(25.0)  # zero actual excluded


def test_model_selection_uses_lower_mae_then_rmse():
    baseline = calculate_metrics([10, 20], [9, 19])
    model = calculate_metrics([10, 20], [10, 20])
    assert select_model(baseline, model) == "xgboost"
    assert select_model(model, baseline) == "naive_baseline"


def test_chronological_split_holds_out_latest_month_only():
    features = build_training_features(supported_series(load_monthly_sales()))
    train, test = chronological_split(features)
    assert max(row.month for row in train) < min(row.month for row in test)
    assert {row.month for row in test} == {date(2024, 3, 1)}


def test_training_evaluates_baseline_and_xgboost_and_writes_metadata(tmp_path):
    features = build_training_features(supported_series(load_monthly_sales()))
    result = train_forecast_model(features, tmp_path)
    assert result.model_path.exists()
    assert result.metadata_path.exists()
    assert result.metadata.baseline_metrics.mae >= 0
    assert result.metadata.model_metrics.rmse >= 0
    assert result.metadata.selected_model in {"naive_baseline", "xgboost"}
    assert result.metadata.training_end_date == date(2024, 3, 1)
    assert result.metadata.feature_names


def test_training_is_reproducible(tmp_path):
    features = build_training_features(supported_series(load_monthly_sales()))
    first = train_forecast_model(features, tmp_path / "one")
    second = train_forecast_model(features, tmp_path / "two")
    assert first.metadata.baseline_metrics == second.metadata.baseline_metrics
    assert first.metadata.model_metrics == second.metadata.model_metrics
    assert first.metadata.selected_model == second.metadata.selected_model


def trained(tmp_path):
    features = build_training_features(supported_series(load_monthly_sales()))
    return train_forecast_model(features, tmp_path)


def test_forecast_generation_is_one_month_ahead_and_grounded(tmp_path):
    result = trained(tmp_path)
    generated = datetime(2026, 9, 15, tzinfo=timezone.utc)
    rows = generate_forecasts(result.model_path, result.metadata_path, load_monthly_sales(), generated_at=generated)
    assert {row.forecast_date for row in rows} == {date(2024, 4, 1)}
    assert len(rows) == 16
    assert all(row.lower_bound <= row.forecast_sales <= row.upper_bound for row in rows)
    assert all(row.model_version == result.metadata.model_version for row in rows)
    assert all(row.training_cutoff_date == date(2024, 3, 1) for row in rows)


def test_forecast_inference_is_deterministic_for_same_artifact(tmp_path):
    result = trained(tmp_path)
    generated = datetime(2026, 9, 15, tzinfo=timezone.utc)
    first = generate_forecasts(result.model_path, result.metadata_path, load_monthly_sales(), generated_at=generated)
    second = generate_forecasts(result.model_path, result.metadata_path, load_monthly_sales(), generated_at=generated)
    assert first == second


def test_local_forecast_persistence_replaces_version_idempotently(tmp_path):
    result = trained(tmp_path / "artifacts")
    rows = generate_forecasts(result.model_path, result.metadata_path, load_monthly_sales())
    writer = LocalForecastWriter(tmp_path / "forecast.duckdb")
    writer.write(rows)
    writer.write(rows)
    assert writer.count() == len(rows)


class FakeQueryService:
    def __init__(self, rows):
        self.rows = rows
        self.sql = []

    def execute_validated(self, sql, context):
        self.sql.append(sql)
        return QueryResult(sql=sql, columns=list(self.rows[0]) if self.rows else [], rows=self.rows)


FORECAST_RECORD = {
    "forecast_date": "2024-04-01",
    "forecast_sales": 82400.5,
    "lower_bound": 78100.2,
    "upper_bound": 86700.8,
    "model_name": "xgboost",
    "model_version": "v1",
    "training_cutoff_date": "2024-03-01",
    "dimension_type": "total",
    "dimension_value": "ALL",
    "generated_at": "2026-09-15T00:00:00+00:00",
    "forecast_horizon": 1,
}


@pytest.mark.parametrize(
    ("dimension_type", "dimension_value"),
    [("total", "ALL"), ("region", "Jawa Barat"), ("product", "Bodrex Flu & Batuk"), ("channel", "Modern Trade")],
)
def test_repository_builds_bounded_dimension_queries(dimension_type, dimension_value):
    service = FakeQueryService([FORECAST_RECORD])
    result = ForecastRepository(service).find(date(2024, 4, 1), dimension_type, dimension_value)
    assert result.status == "ok"
    assert dimension_type in service.sql[0]
    assert dimension_value.replace("'", "''") in service.sql[0]


def test_repository_returns_controlled_missing_forecast():
    result = ForecastRepository(FakeQueryService([])).find(date(2025, 1, 1), "region", "Jawa Barat")
    assert result.status == "FORECAST_NOT_AVAILABLE"
    assert result.rows == []


def test_latest_generated_forecast_version_is_selected():
    service = FakeQueryService([FORECAST_RECORD])
    ForecastRepository(service).find(date(2024, 4, 1), "total", "ALL")
    assert "ORDER BY generated_at DESC" in service.sql[0]
    assert "LIMIT 1" in service.sql[0]


def test_trino_forecast_writer_rejects_arbitrary_table():
    with pytest.raises(ForecastWriteSafetyError):
        TrinoForecastWriter.validate_target("tempo", "commercial", "users")
    assert TrinoForecastWriter.validate_target("tempo", "commercial", "commercial_sales_forecast").endswith("commercial_sales_forecast")


@pytest.mark.parametrize(
    ("question", "dimension_type", "dimension_value"),
    [
        ("Berapa forecast total sales bulan depan?", "total", "ALL"),
        ("Berapa prediksi sales Jawa Barat bulan depan?", "region", "Jawa Barat"),
        ("Forecast Modern Trade bulan depan bagaimana?", "channel", "Modern Trade"),
        ("Prediksi penjualan Bodrex Flu & Batuk bulan depan?", "product", "Bodrex Flu & Batuk"),
    ],
)
def test_forecast_intent_resolves_only_governed_dimensions(question, dimension_type, dimension_value):
    intent = resolve_forecast_intent(question, {}, load_semantic_project())
    assert intent.forecast_period == date(2024, 4, 1)
    assert (intent.dimension_type, intent.dimension_value) == (dimension_type, dimension_value)


def test_forecast_follow_up_preserves_dashboard_filter_context():
    intent = resolve_forecast_intent("Bagaimana forecast bulan depan?", {"filters": {"region": ["Jawa Timur"]}}, load_semantic_project())
    assert (intent.dimension_type, intent.dimension_value) == ("region", "Jawa Timur")


def test_explicit_unavailable_forecast_period_is_preserved():
    intent = resolve_forecast_intent("Forecast Jawa Barat Januari 2025", {}, load_semantic_project())
    assert intent.forecast_period == date(2025, 1, 1)


def test_historical_question_does_not_route_to_forecast():
    assert route_intent({"question": "Kenapa sales Jawa Barat turun bulan ini?"})["intent"] == "analytical"
    assert route_intent({"question": "Berapa forecast Jawa Barat bulan depan?"})["intent"] == "forecast"


def test_forecast_tool_returns_persisted_values_without_numeric_fallback():
    repository = ForecastRepository(FakeQueryService([FORECAST_RECORD]))
    result = ForecastTool(repository).get_sales_forecast(
        resolve_forecast_intent("Forecast total sales bulan depan", {}, load_semantic_project())
    )
    assert result.status == "ok"
    assert result.rows[0].forecast_sales == 82400.5


def test_forecast_tool_missing_result_is_structured_and_number_free():
    repository = ForecastRepository(FakeQueryService([]))
    result = ForecastTool(repository).get_sales_forecast(
        resolve_forecast_intent("Forecast Jawa Barat Januari 2025", {}, load_semantic_project())
    )
    assert result.status == "FORECAST_NOT_AVAILABLE"
    assert result.rows == []


def test_project_owns_eight_forecast_questions_and_unavailable_case():
    questions = load_semantic_project().forecast_golden_questions
    assert len(questions) >= 9
    assert sum(item.expected_status == "FORECAST_NOT_AVAILABLE" for item in questions) >= 1
    assert {item.dimension_type for item in questions}.issuperset({"total", "region", "product", "channel"})


@pytest.mark.asyncio
async def test_missing_forecast_never_invokes_qwen(monkeypatch):
    missing = ForecastLookupResult(status="FORECAST_NOT_AVAILABLE", requested_period=date(2025, 1, 1))

    class MissingTool:
        def get_sales_forecast(self, intent):
            return missing

    monkeypatch.setattr(nodes, "ForecastTool", lambda: MissingTool())
    monkeypatch.setattr(nodes, "get_llm_provider", lambda: pytest.fail("Qwen must not be called"))
    state = await nodes.forecast({"question": "Forecast Jawa Barat Januari 2025", "language": "id", "dashboard_state": {}, "trace_id": "safe"})
    assert state["status"] == "fallback"
    assert state["rows"] == []
    assert "belum tersedia" in state["answer"]["summary"]


@pytest.mark.asyncio
async def test_forecast_node_preserves_tool_numbers_and_builds_chart(monkeypatch):
    row = ForecastRow.model_validate(FORECAST_RECORD)
    lookup = ForecastLookupResult(
        status="ok",
        requested_period=date(2024, 4, 1),
        latest_forecast_period=date(2024, 4, 1),
        latest_actual_period=date(2024, 3, 1),
        rows=[row],
    )

    class AvailableTool:
        def get_sales_forecast(self, intent):
            return lookup

    monkeypatch.setattr(nodes, "ForecastTool", lambda: AvailableTool())
    state = await nodes.forecast({"question": "Forecast total sales bulan depan", "language": "id", "dashboard_state": {}, "trace_id": "safe"})
    assert state["status"] == "ok"
    assert state["rows"][0]["forecast_sales"] == 82400.5
    assert state["chart_spec"]["series"][0]["data"] == [82400.5]
