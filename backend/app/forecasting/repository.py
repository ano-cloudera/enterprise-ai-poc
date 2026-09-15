from __future__ import annotations

from datetime import date
from typing import Literal

from app.forecasting.models import ForecastLookupResult, ForecastRow
from app.services.query import QueryContext, QueryService, query_service


class ForecastRepository:
    def __init__(self, service: QueryService | None = None) -> None:
        self.service = service or query_service

    def find(
        self,
        period: date,
        dimension_type: Literal["total", "region", "product", "channel"],
        dimension_value: str,
    ) -> ForecastLookupResult:
        if dimension_type not in {"total", "region", "product", "channel"}:
            raise ValueError("Unsupported forecast dimension")
        safe_value = dimension_value.replace("'", "''")
        sql = (
            "SELECT forecast_date, generated_at, forecast_horizon, forecast_sales, lower_bound, upper_bound, "
            "model_name, model_version, training_cutoff_date, dimension_type, dimension_value "
            "FROM commercial_sales_forecast "
            f"WHERE forecast_date = DATE '{period.isoformat()}' AND dimension_type = '{dimension_type}' "
            f"AND dimension_value = '{safe_value}' ORDER BY generated_at DESC LIMIT 1"
        )
        try:
            rows = self.service.execute_validated(sql, QueryContext(purpose="forecast.lookup")).rows
        except Exception:
            rows = []
        if not rows:
            return ForecastLookupResult(status="FORECAST_NOT_AVAILABLE", requested_period=period, rows=[])
        return ForecastLookupResult(
            status="ok",
            requested_period=period,
            latest_forecast_period=period,
            latest_actual_period=ForecastRow.model_validate(rows[0]).training_cutoff_date,
            rows=[ForecastRow.model_validate(row) for row in rows],
        )
