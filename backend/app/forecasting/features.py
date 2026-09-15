from __future__ import annotations

from collections import defaultdict
from statistics import stdev
from datetime import date

from app.forecasting.models import FeatureRow, MonthlySales


def build_training_features(rows: list[MonthlySales]) -> list[FeatureRow]:
    groups: dict[tuple[str, str], list[MonthlySales]] = defaultdict(list)
    for row in rows:
        if not row.dimension_type or not row.dimension_value:
            raise ValueError("Feature input must be aggregated to a supported governed series")
        groups[(row.dimension_type, row.dimension_value)].append(row)
    features: list[FeatureRow] = []
    for (dimension_type, dimension_value), series in sorted(groups.items()):
        ordered = sorted(series, key=lambda item: item.month)
        for index in range(3, len(ordered)):
            current = ordered[index]
            prior = [ordered[index - offset].sales_amount for offset in (3, 2, 1)]
            features.append(
                FeatureRow(
                    month=current.month,
                    dimension_type=dimension_type,
                    dimension_value=dimension_value,
                    year=current.month.year,
                    month_number=current.month.month,
                    quarter=(current.month.month - 1) // 3 + 1,
                    month_index=current.month.year * 12 + current.month.month,
                    lag_1=ordered[index - 1].sales_amount,
                    lag_2=ordered[index - 2].sales_amount,
                    lag_3=ordered[index - 3].sales_amount,
                    rolling_mean_3=sum(prior) / 3,
                    rolling_std_3=stdev(prior),
                    target=current.sales_amount,
                )
            )
    return features


def _next_month(value: date) -> date:
    return date(value.year + (value.month == 12), value.month % 12 + 1, 1)


def build_prediction_features(rows: list[MonthlySales]) -> list[FeatureRow]:
    groups: dict[tuple[str, str], list[MonthlySales]] = defaultdict(list)
    for row in rows:
        if not row.dimension_type or not row.dimension_value:
            raise ValueError("Prediction input must be aggregated to a supported governed series")
        groups[(row.dimension_type, row.dimension_value)].append(row)
    result: list[FeatureRow] = []
    for (dimension_type, dimension_value), series in sorted(groups.items()):
        ordered = sorted(series, key=lambda item: item.month)
        if len(ordered) < 3:
            continue
        forecast_month = _next_month(ordered[-1].month)
        prior = [row.sales_amount for row in ordered[-3:]]
        result.append(
            FeatureRow(
                month=forecast_month,
                dimension_type=dimension_type,
                dimension_value=dimension_value,
                year=forecast_month.year,
                month_number=forecast_month.month,
                quarter=(forecast_month.month - 1) // 3 + 1,
                month_index=forecast_month.year * 12 + forecast_month.month,
                lag_1=prior[-1],
                lag_2=prior[-2],
                lag_3=prior[-3],
                rolling_mean_3=sum(prior) / 3,
                rolling_std_3=stdev(prior),
            )
        )
    return result
