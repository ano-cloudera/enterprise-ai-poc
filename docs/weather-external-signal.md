# Historical Weather External Signal

Milestone 6B adds Open-Meteo historical weather as a governed, replaceable external signal. It does not add weather to the Milestone 6A forecast model.

## Governance

Tempo Scan-specific locations and product families live in `projects/tempo_scan/config.yaml` and are validated with Pydantic before use. Weather for one representative city is used as a PoC proxy for each commercial region (for example, Bandung for Jawa Barat). It is not a region-wide measurement. Synthetic commercial values do not represent actual Tempo Scan sales.

The deterministic Weather Analysis Tool joins monthly sales and `commercial_weather_monthly` by governed region/month keys. It calculates comparisons and Pearson correlation from aligned observations. The LLM cannot generate the join or replace calculated values, and correlation is never described as proof of causation.

## Local ingestion

```bash
.venv/bin/python scripts/fetch_weather_history.py
```

The command fetches daily historical observations, validates and aggregates them monthly, and idempotently persists them to `runtime/tempo_scan.duckdb`. It does not connect or write to Trino. Automated tests mock provider data and do not require internet access.

If required weather observations are absent, the controlled response status is `EXTERNAL_SIGNAL_NOT_AVAILABLE`; available historical sales context is returned without estimating weather.
