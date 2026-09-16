from __future__ import annotations

from fastapi import FastAPI, Query

from app.core.config import get_settings
from app.market_intelligence.repository import MarketRepository


def _envelope(data: list[dict], contains_synthetic: bool) -> dict:
    return {
        "status": "ok",
        "data": data,
        "metadata": {
            "source": "market_intelligence_poc",
            "contains_synthetic_data": contains_synthetic,
            "provenance_required": True,
        },
    }


def create_app(repository: MarketRepository | None = None) -> FastAPI:
    repo = repository or MarketRepository(get_settings().duckdb_path)
    app = FastAPI(title="Mock External Market API", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "mock-external-market-api", "market_rows": repo.market_count(), "snapshot_rows": repo.snapshot_count()}

    @app.get("/v1/market/products")
    def products(period: str | None = None, region: str | None = None, category: str | None = None, brand: str | None = None, product: str | None = None):
        rows = repo.list_calibrated(period=period, region=region, category=category, brand=brand, product=product)
        seen, data = set(), []
        for row in rows:
            key = (row.product_name, row.brand, row.category)
            if key not in seen:
                seen.add(key)
                data.append({
                    "product_name": row.product_name, "brand": row.brand, "manufacturer": row.manufacturer,
                    "category": row.category, "competitor_group": row.competitor_group,
                    "source_type": row.source_type, "data_confidence": row.data_confidence,
                })
        return _envelope(data, True)

    @app.get("/v1/market/pricing")
    def pricing(period: str | None = None, region: str | None = None, category: str | None = None, brand: str | None = None, product: str | None = None):
        snapshots = repo.list_snapshots(product_name=product, category=category)
        if snapshots:
            return _envelope([row.model_dump(mode="json") for row in snapshots], False)
        calibrated = repo.list_calibrated(period=period, region=region, category=category, brand=brand, product=product)
        data = [{
            "period": row.period.isoformat(), "region_name": row.region_name, "product_name": row.product_name,
            "brand": row.brand, "avg_market_price": row.avg_market_price,
            "source_type": row.source_type, "data_confidence": row.data_confidence,
        } for row in calibrated]
        return _envelope(data, True)

    @app.get("/v1/market/competitors")
    def competitors(period: str | None = None, region: str | None = None, category: str | None = None, brand: str | None = None, product: str | None = None):
        rows = repo.list_calibrated(period=period, region=region, category=category, brand=brand, product=product)
        data = [row.model_dump(mode="json") for row in rows if "tempo scan" not in row.manufacturer.lower()]
        return _envelope(data, True)

    @app.get("/v1/market/share")
    def share(period: str | None = None, region: str | None = None, category: str | None = None, brand: str | None = None, product: str | None = None):
        return _envelope([row.model_dump(mode="json") for row in repo.list_calibrated(period=period, region=region, category=category, brand=brand, product=product)], True)

    @app.get("/v1/market/opportunity")
    def opportunity(period: str | None = None, region: str | None = None, category: str | None = None, brand: str | None = None, product: str | None = None):
        rows = repo.list_calibrated(period=period, region=region, category=category, brand=brand, product=product)
        return _envelope([row.model_dump(mode="json") for row in rows if "tempo scan" in row.manufacturer.lower()], True)

    return app


app = create_app()
