# Market and Competitive Intelligence Foundation

## Architecture

Serper.dev is used only by the operator-run snapshot collector. Normal application runtime never calls Serper.dev:

```text
Serper.dev -> controlled collector -> validated digital snapshot
        -> calibrated synthetic market dataset -> Mock External Market API
        -> MarketSignalProvider -> deterministic Market Intelligence Tool
        -> controlled LangGraph branch -> Ask AI/dashboard response
```

The Mock External Market API runs separately on port 8100 and is configured in the main application with `MARKET_API_BASE_URL`. This boundary permits later replacement by IQVIA, NielsenIQ, Euromonitor, marketplace/search intelligence APIs, or customer-owned research data. None of those providers is currently integrated.

## Collection and snapshot strategy

`scripts/fetch_market_snapshot.py` sends a bounded number of Google Shopping requests using `SERPER_API_KEY` in the `X-API-KEY` header. During migration, the script can read the legacy `SERPAPI_API_KEY` variable. The key is environment-only, is never logged, and is not exposed to LangGraph. Results are normalized, Pydantic-validated, deduplicated, and persisted with observation/source metadata. Raw Serper.dev structures do not enter the application graph. A failed collection never clears the previous valid snapshot.

Observed snapshot fields include search result title, seller, observed/old price, discount, rating, review count, position, availability, query, and timestamp when returned by the provider. Serper.dev records use `source_type=serper_snapshot` and `data_confidence=observed`.

The collector conservatively derives `package_type`, `package_quantity`, `unit_type`, and `normalized_unit_price` from unambiguous titles. Each row includes `normalization_confidence`. Ambiguous titles keep the original observed price while all derived package fields remain null; raw prices from unlike package groups are never treated as directly comparable.

## Calibrated market indicators

`commercial_market_monthly` contains deterministic PoC values for estimated market value/volume, market share, growth, average price, promotion, distribution, visibility, competitive pressure, and opportunity. These always use `source_type=synthetic_calibrated` and `data_confidence=calibrated`. They are not measured market share or competitor sales and are not licensed-provider data.

Average price uses the latest persisted snapshot for each product. Calibration prefers a median normalized unit price with at least two comparable observations, then a median raw price within one matching package group. A deterministic adjustment of no more than ±5% is applied around that anchor. When neither method is supported, calibration uses the existing deterministic synthetic fallback. `price_anchor_source`, `price_anchor_method`, and `price_anchor_value` make that distinction explicit.

Category-level directional constraints are declared in `projects/tempo_scan/market_intelligence.yaml`. The Adult Analgesic PoC scenario requires Bodrex and Oskadon to have at least 55% combined synthetic share, while every category remains normalized to 100%. This is a transparent scenario constraint—not an assertion of measured IQVIA, NielsenIQ, or public market share.

The opportunity score is a 0–100 average of normalized market growth, market size, Tempo share gap, distribution gap, and competitive pressure components. Both the result and components are returned. This is a transparent PoC indicator, not an official commercial scoring methodology or universal industry standard.

## Separate API

- `GET /health`
- `GET /v1/market/products`
- `GET /v1/market/pricing`
- `GET /v1/market/competitors`
- `GET /v1/market/share`
- `GET /v1/market/opportunity`

Endpoints support relevant `period`, `region`, `category`, `brand`, and `product` filters and return provenance metadata. Start locally with `bash scripts/run-market-api.sh`.

## Limitations

Digital search results represent a time-bound online observation, not total market measurement. Calibrated data must be replaced or validated against licensed or customer-owned sources for production. Relationships do not establish causation. Market/weather signals are not forecast features in Milestone 6C.
