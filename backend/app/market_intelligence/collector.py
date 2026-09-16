from __future__ import annotations

from datetime import datetime, timezone

from app.market_intelligence.models import MarketGovernance, SnapshotCollectionReport
from app.market_intelligence.providers.serpapi import SerpApiUnavailable
from app.market_intelligence.providers.serper import SerperDevUnavailable


class MarketSnapshotCollector:
    """Operator-only snapshot collector. Runtime code never constructs this class."""

    def __init__(self, provider, repository, governance: MarketGovernance) -> None:
        self.provider = provider
        self.repository = repository
        self.governance = governance

    def collect(self, max_queries: int = 5, observed_at: datetime | None = None) -> SnapshotCollectionReport:
        timestamp = observed_at or datetime.now(timezone.utc)
        products = [item for item in self.governance.products if item.priority][:max(1, min(max_queries, 11))]
        if getattr(self.provider, "configured", True) is False:
            return SnapshotCollectionReport(
                queries_sent=0, normalized_results=0, products_observed=[],
                missing_products=[item.product_name for item in products], failures=[], snapshot_at=timestamp,
            )
        collected = []
        observed, missing, failures = [], [], []
        for product in products:
            try:
                rows = self.provider.collect(
                    query=f"{product.product_name} harga", product_name=product.product_name,
                    category=product.category, observed_at=timestamp,
                )
            except (SerpApiUnavailable, SerperDevUnavailable):
                failures.append(product.product_name)
                continue
            if rows:
                collected.extend(rows)
                observed.append(product.product_name)
            else:
                missing.append(product.product_name)
        # Persist only validated successful records. An all-failure run never clears
        # the previous valid snapshot.
        if collected:
            self.repository.upsert_snapshots(collected)
        return SnapshotCollectionReport(
            queries_sent=len(products), normalized_results=len(collected), products_observed=observed,
            missing_products=missing, failures=failures, snapshot_at=timestamp,
        )
