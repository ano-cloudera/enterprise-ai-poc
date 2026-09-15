from __future__ import annotations

from datetime import date
import re

from app.forecasting.models import ForecastIntent, ForecastLookupResult
from app.forecasting.repository import ForecastRepository
from app.semantic.models import SemanticProject


_MONTHS = {
    "januari": 1, "january": 1, "februari": 2, "february": 2, "maret": 3, "march": 3,
    "april": 4, "mei": 5, "may": 5, "juni": 6, "june": 6, "juli": 7, "july": 7,
    "agustus": 8, "august": 8, "september": 9, "oktober": 10, "october": 10,
    "november": 11, "desember": 12, "december": 12,
}


def _default_forecast_period(project: SemanticProject) -> date:
    current = project.resolution.period_ranges.get("current_month")
    if not current:
        raise ValueError("Current governed period is not configured")
    end = date.fromisoformat(current.end)
    return end.replace(day=1)


def _explicit_period(question: str) -> date | None:
    lowered = question.lower()
    year = re.search(r"\b(20\d{2})\b", lowered)
    if not year:
        return None
    for name, month in _MONTHS.items():
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            return date(int(year.group(1)), month, 1)
    return None


def resolve_forecast_intent(question: str, dashboard_state: dict, project: SemanticProject) -> ForecastIntent:
    lowered = question.lower()
    period = _explicit_period(question) or _default_forecast_period(project)
    if "total" in lowered:
        return ForecastIntent(forecast_period=period, dimension_type="total", dimension_value="ALL")
    for dimension_type in ("region", "product", "channel"):
        for entity in project.resolution.entities.get(dimension_type, []):
            for alias in [entity.value, *entity.aliases]:
                if re.search(rf"(?<!\w){re.escape(alias.lower())}(?!\w)", lowered):
                    return ForecastIntent(forecast_period=period, dimension_type=dimension_type, dimension_value=entity.value)
    if any(term in lowered for term in ("produk mana", "which product", "produk tertinggi")):
        return ForecastIntent(forecast_period=period, dimension_type="product", dimension_value=None, top_n=5)
    filters = dashboard_state.get("filters") or {}
    for dimension_type in ("region", "product", "channel"):
        values = filters.get(dimension_type) or []
        if values:
            governed = {entity.value for entity in project.resolution.entities.get(dimension_type, [])}
            if values[0] in governed:
                return ForecastIntent(forecast_period=period, dimension_type=dimension_type, dimension_value=values[0])
    return ForecastIntent(forecast_period=period, dimension_type="total", dimension_value="ALL")


class ForecastTool:
    def __init__(self, repository: ForecastRepository | None = None) -> None:
        self.repository = repository or ForecastRepository()

    def get_sales_forecast(self, intent: ForecastIntent) -> ForecastLookupResult:
        if intent.top_n:
            return self.repository.top(intent.forecast_period, intent.dimension_type, intent.top_n)
        return self.repository.find(intent.forecast_period, intent.dimension_type, intent.dimension_value or "")
