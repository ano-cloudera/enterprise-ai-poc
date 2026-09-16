from __future__ import annotations

import httpx


class MarketSignalUnavailable(RuntimeError):
    pass


class MockExternalMarketApiProvider:
    def __init__(self, base_url: str, client=None, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def _get(self, endpoint: str, **filters) -> list[dict]:
        try:
            response = self.client.get(
                f"{self.base_url}/v1/market/{endpoint}",
                params={key: value for key, value in filters.items() if value is not None},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "ok" or not isinstance(payload.get("data"), list):
                raise ValueError("invalid response")
            return payload["data"]
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            raise MarketSignalUnavailable("EXTERNAL_MARKET_SIGNAL_NOT_AVAILABLE") from None

    def get_market_share(self, **filters) -> list[dict]:
        return self._get("share", **filters)

    def get_competitors(self, **filters) -> list[dict]:
        return self._get("competitors", **filters)

    def get_pricing(self, **filters) -> list[dict]:
        return self._get("pricing", **filters)

    def get_opportunity(self, **filters) -> list[dict]:
        return self._get("opportunity", **filters)

