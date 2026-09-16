from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import duckdb

from app.market_intelligence.models import DigitalMarketSignal, MarketMonthly


class MarketRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _create(connection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS commercial_market_digital_snapshot ("
            "observed_at TIMESTAMPTZ, query VARCHAR, product_name VARCHAR, category VARCHAR, seller VARCHAR, title VARCHAR, "
            "observed_price DOUBLE, old_price DOUBLE, discount_pct DOUBLE, rating DOUBLE, review_count BIGINT, "
            "search_position BIGINT, availability VARCHAR, source VARCHAR, source_type VARCHAR, data_confidence VARCHAR, "
            "PRIMARY KEY (observed_at, query, product_name, seller, title))"
        )
        for definition in (
            "package_type VARCHAR",
            "package_quantity BIGINT",
            "unit_type VARCHAR",
            "normalized_unit_price DOUBLE",
            "normalization_confidence VARCHAR DEFAULT 'low'",
        ):
            connection.execute(
                f"ALTER TABLE commercial_market_digital_snapshot ADD COLUMN IF NOT EXISTS {definition}"
            )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS commercial_market_monthly ("
            "period DATE, region_name VARCHAR, category VARCHAR, product_name VARCHAR, brand VARCHAR, manufacturer VARCHAR, "
            "competitor_group VARCHAR, estimated_market_value DOUBLE, estimated_market_volume DOUBLE, market_share_pct DOUBLE, "
            "market_growth_pct DOUBLE, avg_market_price DOUBLE, promo_intensity_index DOUBLE, distribution_coverage_pct DOUBLE, "
            "digital_visibility_index DOUBLE, competitive_pressure_index DOUBLE, opportunity_score DOUBLE, opportunity_components VARCHAR, "
            "source_type VARCHAR, data_confidence VARCHAR, generated_at TIMESTAMPTZ, "
            "PRIMARY KEY (period, region_name, category, product_name, brand, source_type))"
        )
        for definition in (
            "price_anchor_source VARCHAR DEFAULT 'synthetic_fallback'",
            "price_anchor_method VARCHAR DEFAULT 'deterministic_synthetic'",
            "price_anchor_value DOUBLE",
        ):
            connection.execute(
                f"ALTER TABLE commercial_market_monthly ADD COLUMN IF NOT EXISTS {definition}"
            )

    def upsert_snapshots(self, rows: list[DigitalMarketSignal]) -> None:
        if not rows:
            return
        with duckdb.connect(str(self.path)) as connection:
            self._create(connection)
            connection.executemany(
                "INSERT OR REPLACE INTO commercial_market_digital_snapshot ("
                "observed_at, query, product_name, category, seller, title, observed_price, old_price, discount_pct, "
                "rating, review_count, search_position, availability, source, source_type, data_confidence, "
                "package_type, package_quantity, unit_type, normalized_unit_price, normalization_confidence"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(
                    row.observed_at, row.query, row.product_name, row.category, row.seller or "", row.title,
                    row.observed_price, row.old_price, row.discount_pct, row.rating, row.review_count,
                    row.search_position, row.availability, row.source, row.source_type, row.data_confidence,
                    row.package_type, row.package_quantity, row.unit_type, row.normalized_unit_price,
                    row.normalization_confidence,
                ) for row in rows],
            )

    def list_snapshots(self, **filters) -> list[DigitalMarketSignal]:
        clauses, values = [], []
        allowed = {"product_name", "category", "seller"}
        for key, value in filters.items():
            if key in allowed and value:
                clauses.append(f"{key} = ?")
                values.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with duckdb.connect(str(self.path)) as connection:
            self._create(connection)
            cursor = connection.execute(
                "SELECT * FROM commercial_market_digital_snapshot" + where + " ORDER BY observed_at DESC, search_position", values
            )
            columns = [item[0] for item in cursor.description]
            records = cursor.fetchall()
        parsed = []
        for record in records:
            raw = dict(zip(columns, record))
            raw["seller"] = raw["seller"] or None
            parsed.append(DigitalMarketSignal.model_validate(raw))
        return parsed

    def list_latest_snapshots(self) -> list[DigitalMarketSignal]:
        """Return the newest complete collection timestamp for each product."""
        rows = self.list_snapshots()
        latest = {}
        for row in rows:
            latest.setdefault(row.product_name, row.observed_at)
        return [row for row in rows if row.observed_at == latest[row.product_name]]

    def snapshot_count(self) -> int:
        with duckdb.connect(str(self.path)) as connection:
            self._create(connection)
            return int(connection.execute("SELECT COUNT(*) FROM commercial_market_digital_snapshot").fetchone()[0])

    def replace_calibrated(self, rows: list[MarketMonthly]) -> None:
        if not rows:
            return
        with duckdb.connect(str(self.path)) as connection:
            self._create(connection)
            connection.execute("DELETE FROM commercial_market_monthly")
            connection.executemany(
                "INSERT INTO commercial_market_monthly ("
                "period, region_name, category, product_name, brand, manufacturer, competitor_group, "
                "estimated_market_value, estimated_market_volume, market_share_pct, market_growth_pct, avg_market_price, "
                "promo_intensity_index, distribution_coverage_pct, digital_visibility_index, competitive_pressure_index, "
                "opportunity_score, opportunity_components, source_type, data_confidence, generated_at, "
                "price_anchor_source, price_anchor_method, price_anchor_value"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(
                    row.period, row.region_name, row.category, row.product_name, row.brand, row.manufacturer,
                    row.competitor_group, row.estimated_market_value, row.estimated_market_volume, row.market_share_pct,
                    row.market_growth_pct, row.avg_market_price, row.promo_intensity_index,
                    row.distribution_coverage_pct, row.digital_visibility_index, row.competitive_pressure_index,
                    row.opportunity_score, json.dumps(row.opportunity_components.model_dump(), sort_keys=True),
                    row.source_type, row.data_confidence, row.generated_at,
                    row.price_anchor_source, row.price_anchor_method, row.price_anchor_value,
                ) for row in rows],
            )

    def list_calibrated(self, **filters) -> list[MarketMonthly]:
        clauses, values = [], []
        aliases = {"period": "period", "region": "region_name", "category": "category", "brand": "brand", "product": "product_name"}
        for key, column in aliases.items():
            value = filters.get(key)
            if value:
                clauses.append(f"{column} = ?")
                values.append(date.fromisoformat(value) if key == "period" and isinstance(value, str) else value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with duckdb.connect(str(self.path)) as connection:
            self._create(connection)
            cursor = connection.execute(
                "SELECT * FROM commercial_market_monthly" + where + " ORDER BY opportunity_score DESC, region_name, brand", values
            )
            columns = [item[0] for item in cursor.description]
            records = cursor.fetchall()
        parsed = []
        for record in records:
            raw = dict(zip(columns, record))
            raw["opportunity_components"] = json.loads(raw["opportunity_components"])
            parsed.append(MarketMonthly.model_validate(raw))
        return parsed

    def market_count(self) -> int:
        with duckdb.connect(str(self.path)) as connection:
            self._create(connection)
            return int(connection.execute("SELECT COUNT(*) FROM commercial_market_monthly").fetchone()[0])
