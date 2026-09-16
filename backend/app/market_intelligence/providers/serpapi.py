from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.market_intelligence.models import DigitalMarketSignal
from app.market_intelligence.normalization import normalize_serpapi_results


class SerpApiUnavailable(RuntimeError):
    pass


class SerpApiMarketProvider:
    endpoint = "https://serpapi.com/search.json"

    def __init__(self, api_key: str, enabled: bool = True, client=None, result_limit: int = 10) -> None:
        self._api_key = api_key
        self.enabled = enabled
        self.client = client or httpx.Client(timeout=30.0)
        self.result_limit = min(max(result_limit, 1), 20)

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self._api_key)

    def collect(self, query: str, product_name: str, category: str, observed_at: datetime | None = None) -> list[DigitalMarketSignal]:
        if not self.configured:
            raise SerpApiUnavailable("SERPAPI_NOT_CONFIGURED")
        timestamp = observed_at or datetime.now(timezone.utc)
        try:
            response = self.client.get(self.endpoint, params={
                "engine": "google_shopping", "q": query, "api_key": self._api_key,
                "gl": "id", "hl": "id", "num": self.result_limit,
            })
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise SerpApiUnavailable("SERPAPI_REQUEST_FAILED") from None
        if payload.get("error"):
            raise SerpApiUnavailable("SERPAPI_REQUEST_FAILED")
        return normalize_serpapi_results(payload, query, product_name, category, timestamp, self.result_limit)
