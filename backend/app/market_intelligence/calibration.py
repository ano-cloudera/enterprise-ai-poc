from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
from statistics import median

from app.market_intelligence.models import DigitalMarketSignal, MarketGovernance, MarketMonthly, OpportunityComponents, PriceAnchor


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, value))


def _unit(*parts: object) -> float:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big") / (2**64 - 1)


def opportunity_score(
    *, market_growth_pct: float, market_size: float, market_share_pct: float,
    distribution_coverage_pct: float, competitive_pressure_index: float,
) -> tuple[float, dict[str, float]]:
    components = {
        "growth": _bounded((market_growth_pct + 5) * 5),
        "market_size": _bounded(market_size / 3000),
        "share_gap": _bounded(100 - market_share_pct),
        "distribution_gap": _bounded(100 - distribution_coverage_pct),
        "competitive_pressure": _bounded(competitive_pressure_index),
    }
    return sum(components.values()) / len(components), components


def _months(start: date, end: date):
    current = start.replace(day=1)
    while current <= end.replace(day=1):
        yield current
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)


def build_price_anchors(signals: list[DigitalMarketSignal]) -> dict[str, PriceAnchor]:
    by_product: dict[str, list[DigitalMarketSignal]] = defaultdict(list)
    for signal in signals:
        by_product[signal.product_name].append(signal)
    anchors = {}
    for product, rows in by_product.items():
        normalized_groups: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            if row.normalized_unit_price and row.unit_type and row.normalization_confidence in {"high", "medium"}:
                normalized_groups[row.unit_type].append(row.normalized_unit_price)
        unit_priority = {"tablet": 5, "capsule": 4, "sachet": 3, "bottle": 2, "strip": 1, "box": 0, "pack": 0}
        comparable = max(
            normalized_groups.items(),
            key=lambda item: (len(item[1]), unit_priority.get(item[0], 0)),
            default=(None, []),
        )
        if len(comparable[1]) >= 2:
            anchors[product] = PriceAnchor(
                value=median(comparable[1]), method="median_normalized_unit_price",
                unit_type=comparable[0], observation_count=len(comparable[1]),
            )
            continue
        observed_groups: dict[tuple, list[float]] = defaultdict(list)
        for row in rows:
            if row.observed_price and row.package_type:
                observed_groups[(row.package_type, row.package_quantity, row.unit_type)].append(row.observed_price)
        observed = max(observed_groups.items(), key=lambda item: len(item[1]), default=(None, []))
        if len(observed[1]) >= 2:
            anchors[product] = PriceAnchor(
                value=median(observed[1]), method="median_observed_price",
                unit_type=observed[0][2], observation_count=len(observed[1]),
            )
    return anchors


def generate_calibrated_market(
    governance: MarketGovernance, start: date, end: date, generated_at: datetime | None = None,
    observed_signals: list[DigitalMarketSignal] | None = None,
) -> list[MarketMonthly]:
    generated = generated_at or datetime.now(timezone.utc)
    anchors = build_price_anchors(observed_signals or [])
    products_by_category = defaultdict(list)
    competitors_by_category = defaultdict(list)
    for item in governance.products:
        products_by_category[item.category].append(item)
    for item in governance.competitors:
        competitors_by_category[item.category].append(item)
    rows: list[MarketMonthly] = []
    for period in _months(start, end):
        for region in governance.regions:
            for category in sorted(products_by_category):
                entries = [
                    (item.product_name, item.brand, item.manufacturer, item.competitor_group)
                    for item in products_by_category[category]
                ] + [
                    (item.brand, item.brand, item.manufacturer, item.competitor_group)
                    for item in competitors_by_category[category]
                ]
                weights = [0.5 + _unit(period, region, category, brand, "share") for _, brand, _, _ in entries]
                shares = [weight * 100 / sum(weights) for weight in weights]
                constraint = governance.category_constraints.get(category)
                if constraint:
                    leader_indices = [index for index, entry in enumerate(entries) if entry[1] in constraint.leader_group_brands]
                    leader_share = sum(shares[index] for index in leader_indices)
                    minimum = constraint.minimum_combined_share_pct
                    if leader_indices and leader_share < minimum:
                        # Tiny headroom avoids binary floating-point rounding below
                        # the governed inclusive minimum.
                        target = min(100.0, minimum + 1e-9)
                        for index in range(len(shares)):
                            if index in leader_indices:
                                shares[index] *= target / leader_share
                            else:
                                shares[index] *= (100 - target) / (100 - leader_share)
                shares[-1] = 100 - sum(shares[:-1])
                total_market = 120000 + 180000 * _unit(period, region, category, "market")
                growth = -2 + 17 * _unit(period, region, category, "growth")
                for (product, brand, manufacturer, group), share in zip(entries, shares):
                    anchor = anchors.get(product)
                    if anchor:
                        price = anchor.value * (0.95 + 0.10 * _unit(period, region, product, "price-adjustment"))
                        price_anchor_source = "serper_snapshot"
                        price_anchor_method = anchor.method
                        price_anchor_value = anchor.value
                    else:
                        price = 10000 + 90000 * _unit(category, brand, "price")
                        price_anchor_source = "synthetic_fallback"
                        price_anchor_method = "deterministic_synthetic"
                        price_anchor_value = None
                    promo = 20 + 70 * _unit(period, region, brand, "promo")
                    coverage = 35 + 60 * _unit(period, region, brand, "coverage")
                    visibility = 15 + 80 * _unit(period, region, brand, "visibility")
                    pressure = _bounded((100 - share) * 0.45 + promo * 0.25 + visibility * 0.30)
                    score, components = opportunity_score(
                        market_growth_pct=growth, market_size=total_market, market_share_pct=share,
                        distribution_coverage_pct=coverage, competitive_pressure_index=pressure,
                    )
                    value = total_market * share / 100
                    rows.append(MarketMonthly(
                        period=period, region_name=region, category=category, product_name=product,
                        brand=brand, manufacturer=manufacturer, competitor_group=group,
                        estimated_market_value=value, estimated_market_volume=value * 1_000_000 / price,
                        market_share_pct=share, market_growth_pct=growth, avg_market_price=price,
                        promo_intensity_index=promo, distribution_coverage_pct=coverage,
                        digital_visibility_index=visibility, competitive_pressure_index=pressure,
                        opportunity_score=score, opportunity_components=OpportunityComponents.model_validate(components),
                        price_anchor_source=price_anchor_source, price_anchor_method=price_anchor_method,
                        price_anchor_value=price_anchor_value,
                        generated_at=generated,
                    ))
    return rows
