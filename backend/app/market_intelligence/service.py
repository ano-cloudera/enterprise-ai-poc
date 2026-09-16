from __future__ import annotations

from collections import defaultdict
from datetime import date
from functools import lru_cache
import re

import yaml

from app.core.config import get_settings
from app.forecasting.data import load_monthly_sales
from app.market_intelligence.models import MarketGovernance, MarketIntent, MarketResult
from app.market_intelligence.providers.mock_api import MarketSignalUnavailable, MockExternalMarketApiProvider
from app.semantic.models import SemanticProject


@lru_cache(maxsize=8)
def load_market_governance(project_id: str = "tempo_scan") -> MarketGovernance:
    path = get_settings().project_root / project_id / "market_intelligence.yaml"
    with path.open(encoding="utf-8") as handle:
        return MarketGovernance.model_validate(yaml.safe_load(handle) or {})


def _contains(text: str, value: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(value.lower())}(?!\w)", text) is not None


def resolve_market_intent(
    question: str, dashboard_state: dict, project: SemanticProject, governance: MarketGovernance,
) -> MarketIntent:
    lowered = question.lower()
    product = next((item.product_name for item in sorted(governance.products, key=lambda value: len(value.product_name), reverse=True) if _contains(lowered, item.product_name)), None)
    region = next((item for item in governance.regions if _contains(lowered, item)), None)
    category = next((item.category for item in governance.products if _contains(lowered, item.category)), None)
    filters = dashboard_state.get("filters") or {}
    governed_products = {item.product_name for item in governance.products}
    product_context = (filters.get("product") or [None])[0]
    region_context = (filters.get("region") or [None])[0]
    product = product or (product_context if product_context in governed_products else None)
    region = region or (region_context if region_context in governance.regions else None)
    if "opportunity" in lowered or "menarik" in lowered:
        analysis_type = "opportunity"
    elif any(term in lowered for term in ("price", "harga")):
        analysis_type = "pricing"
    elif "distribution gap" in lowered or "distribusi" in lowered:
        analysis_type = "distribution"
    elif any(term in lowered for term in ("kompetitor", "competitor", "pesaing")):
        analysis_type = "position" if "posisi" in lowered else "competitors"
    elif any(term in lowered for term in ("competitive pressure", "tekanan kompetitif")):
        analysis_type = "sales_pressure" if any(term in lowered for term in ("sales", "turun", "penjualan")) else "pressure"
    elif any(term in lowered for term in ("market share", "share")):
        analysis_type = "share"
    elif any(term in lowered for term in ("tumbuh", "growth", "pertumbuhan")):
        analysis_type = "growth"
    else:
        analysis_type = "position"
    current = project.resolution.period_ranges.get("current_month")
    period = date.fromisoformat(current.start) if current else date(2024, 3, 1)
    return MarketIntent(analysis_type=analysis_type, period=period, product_name=product, region_name=region, category=category)


class MarketIntelligenceTool:
    def __init__(self, provider=None, sales_loader=load_monthly_sales) -> None:
        self.provider = provider or MockExternalMarketApiProvider(get_settings().market_api_base_url)
        self.sales_loader = sales_loader

    def _sales_evidence(self, intent: MarketIntent) -> list[dict]:
        if intent.analysis_type != "sales_pressure" or not intent.product_name:
            return []
        totals = defaultdict(float)
        for row in self.sales_loader():
            if row.product_name == intent.product_name and (not intent.region_name or row.region_name == intent.region_name):
                totals[row.month] += row.sales_amount
        current = totals.get(intent.period)
        previous_month = date(intent.period.year - (intent.period.month == 1), 12 if intent.period.month == 1 else intent.period.month - 1, 1)
        previous = totals.get(previous_month)
        if current is None or previous is None:
            return []
        return [{
            "period": intent.period.isoformat(), "sales_current": current, "sales_previous": previous,
            "sales_change_pct": None if previous == 0 else (current / previous - 1) * 100,
            "source_type": "internal_governed_sales", "data_confidence": "observed",
        }]

    def analyze(self, intent: MarketIntent) -> MarketResult:
        governed_product = next(
            (item for item in load_market_governance().products if item.product_name == intent.product_name), None
        )
        category = intent.category or (governed_product.category if governed_product else None)
        filters = {
            "period": intent.period.isoformat(), "region": intent.region_name,
            "category": category,
            "product": None if intent.analysis_type in {"position", "competitors"} else intent.product_name,
        }
        method_name = {
            "competitors": "get_competitors",
            "pricing": "get_pricing",
            "opportunity": "get_opportunity",
        }.get(intent.analysis_type, "get_market_share")
        try:
            method = getattr(self.provider, method_name)
            evidence = method(**filters)
        except (MarketSignalUnavailable, AttributeError):
            return MarketResult(
                status="EXTERNAL_MARKET_SIGNAL_NOT_AVAILABLE", analysis_type=intent.analysis_type,
                requested_product=intent.product_name, requested_region=intent.region_name,
                evidence=[], metadata={"contains_synthetic_data": False},
            )
        if not evidence:
            return MarketResult(
                status="MARKET_DATA_NOT_AVAILABLE", analysis_type=intent.analysis_type,
                requested_product=intent.product_name, requested_region=intent.region_name,
                evidence=[], metadata={"contains_synthetic_data": False},
            )
        synthetic = any(item.get("source_type") == "synthetic_calibrated" for item in evidence)
        return MarketResult(
            status="ok", analysis_type=intent.analysis_type, requested_product=intent.product_name,
            requested_region=intent.region_name, evidence=evidence, internal_sales_evidence=self._sales_evidence(intent),
            metadata={"contains_synthetic_data": synthetic, "metrics_immutable": True},
        )
