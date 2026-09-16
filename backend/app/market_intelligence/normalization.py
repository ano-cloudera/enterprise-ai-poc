from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from app.market_intelligence.models import DigitalMarketSignal, PackageNormalization


_UNIT_ALIASES = {
    "tablet": "tablet", "tablets": "tablet", "tab": "tablet", "kaplet": "tablet",
    "capsule": "capsule", "capsules": "capsule", "kapsul": "capsule",
    "sachet": "sachet", "sachets": "sachet", "strip": "strip",
    "bottle": "bottle", "botol": "bottle", "box": "box", "pack": "pack",
}


def parse_package(title: str, observed_price: float | None) -> PackageNormalization:
    text = title.casefold().replace("×", "x")
    package_match = re.search(r"\b(box|strip|sachet|bottle|botol|pack)\b", text)
    package_type = _UNIT_ALIASES[package_match.group(1)] if package_match else None
    nested = re.search(
        r"\b(\d+)\s*(strip|sachet|pack)\s*(?:x|@)\s*(\d+)\s*(tablet|tablets|tab|kaplet|capsule|capsules|kapsul)\b",
        text,
    )
    if nested:
        quantity = int(nested.group(1)) * int(nested.group(3))
        unit_type = _UNIT_ALIASES[nested.group(4)]
    else:
        direct = re.search(
            r"(?<![-\w])(\d+)\s*(tablet|tablets|tab|kaplet|capsule|capsules|kapsul|sachet|sachets|strip|bottle|botol|box|pack)\b",
            text,
        )
        if not direct:
            return PackageNormalization(normalization_confidence="low")
        quantity = int(direct.group(1))
        unit_type = _UNIT_ALIASES[direct.group(2)]
        package_type = package_type or (unit_type if unit_type in {"box", "bottle", "strip", "sachet"} else "pack")
    if quantity < 1:
        return PackageNormalization(normalization_confidence="low")
    return PackageNormalization(
        package_type=package_type, package_quantity=quantity, unit_type=unit_type,
        normalized_unit_price=(observed_price / quantity) if observed_price is not None else None,
        normalization_confidence="high" if observed_price is not None else "medium",
    )


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^0-9,.-]", "", str(value))
    if not text:
        return None
    if "." in text and "," not in text and len(text.rsplit(".", 1)[-1]) == 3:
        text = text.replace(".", "")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def normalize_serpapi_results(
    payload: dict[str, Any], query: str, product_name: str, category: str,
    observed_at: datetime, limit: int = 10,
) -> list[DigitalMarketSignal]:
    normalized: list[DigitalMarketSignal] = []
    seen: set[tuple] = set()
    for item in (payload.get("shopping_results") or payload.get("organic_results") or []):
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        seller = item.get("source") or item.get("seller")
        price = _number(item.get("extracted_price")) or _number(item.get("price"))
        old_price = _number(item.get("extracted_old_price")) or _number(item.get("old_price"))
        key = (title.casefold(), str(seller or "").casefold(), price)
        if key in seen:
            continue
        seen.add(key)
        discount = _number(item.get("discount"))
        if discount is None and price is not None and old_price and old_price > 0:
            discount = max(0.0, min(100.0, (old_price - price) * 100 / old_price))
        package = parse_package(title, price)
        normalized.append(DigitalMarketSignal(
            observed_at=observed_at, query=query, product_name=product_name, category=category,
            seller=str(seller).strip() if seller else None, title=title, observed_price=price,
            old_price=old_price, discount_pct=discount, rating=_number(item.get("rating")),
            review_count=int(value) if (value := _number(item.get("reviews") or item.get("review_count"))) is not None else None,
            search_position=int(value) if (value := _number(item.get("position"))) is not None else None,
            availability=str(item.get("availability") or item.get("delivery") or "unknown"),
            **package.model_dump(),
        ))
        if len(normalized) >= max(1, min(limit, 20)):
            break
    return normalized


def normalize_serper_results(
    payload: dict[str, Any], query: str, product_name: str, category: str,
    observed_at: datetime, limit: int = 10,
) -> list[DigitalMarketSignal]:
    adapted = []
    for item in payload.get("shopping") or []:
        adapted.append({
            "title": item.get("title"),
            "source": item.get("source") or item.get("seller"),
            "extracted_price": item.get("extractedPrice") or item.get("price"),
            "extracted_old_price": item.get("extractedOldPrice") or item.get("oldPrice"),
            "rating": item.get("rating"),
            "reviews": item.get("ratingCount") or item.get("reviews"),
            "position": item.get("position"),
            "delivery": item.get("delivery"),
            "availability": item.get("availability"),
        })
    rows = normalize_serpapi_results(
        {"shopping_results": adapted}, query, product_name, category, observed_at, limit,
    )
    return [row.model_copy(update={"source": "serper_dev", "source_type": "serper_snapshot"}) for row in rows]
