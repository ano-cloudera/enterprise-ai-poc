from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DigitalMarketSignal(FrozenModel):
    observed_at: datetime
    query: str
    product_name: str
    category: str
    seller: str | None = None
    title: str
    observed_price: float | None = Field(default=None, ge=0)
    old_price: float | None = Field(default=None, ge=0)
    discount_pct: float | None = Field(default=None, ge=0, le=100)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    search_position: int | None = Field(default=None, ge=1)
    availability: str | None = None
    package_type: str | None = None
    package_quantity: int | None = Field(default=None, ge=1)
    unit_type: str | None = None
    normalized_unit_price: float | None = Field(default=None, ge=0)
    normalization_confidence: Literal["high", "medium", "low"] = "low"
    source: Literal["serpapi", "serper_dev"] = "serpapi"
    source_type: Literal["serpapi_snapshot", "serper_snapshot"] = "serpapi_snapshot"
    data_confidence: Literal["observed"] = "observed"


class MarketProduct(FrozenModel):
    product_name: str
    brand: str
    manufacturer: str
    category: str
    competitor_group: str
    priority: bool = True


class MarketCompetitor(FrozenModel):
    brand: str
    manufacturer: str
    category: str
    competitor_group: str


class CategoryConstraint(FrozenModel):
    leader_group_brands: list[str] = Field(min_length=1)
    minimum_combined_share_pct: float = Field(gt=0, lt=100)
    calibration_note: str


class MarketGovernance(FrozenModel):
    synthetic_data_disclaimer: str
    opportunity_methodology_disclaimer: str
    regions: list[str] = Field(min_length=1)
    products: list[MarketProduct] = Field(min_length=1)
    competitors: list[MarketCompetitor] = Field(min_length=1)
    category_constraints: dict[str, CategoryConstraint] = Field(default_factory=dict)


class PackageNormalization(FrozenModel):
    package_type: str | None = None
    package_quantity: int | None = Field(default=None, ge=1)
    unit_type: str | None = None
    normalized_unit_price: float | None = Field(default=None, ge=0)
    normalization_confidence: Literal["high", "medium", "low"] = "low"


class PriceAnchor(FrozenModel):
    value: float = Field(gt=0)
    method: Literal["median_normalized_unit_price", "median_observed_price"]
    unit_type: str | None = None
    observation_count: int = Field(ge=2)


class OpportunityComponents(FrozenModel):
    growth: float = Field(ge=0, le=100)
    market_size: float = Field(ge=0, le=100)
    share_gap: float = Field(ge=0, le=100)
    distribution_gap: float = Field(ge=0, le=100)
    competitive_pressure: float = Field(ge=0, le=100)


class MarketMonthly(FrozenModel):
    period: date
    region_name: str
    category: str
    product_name: str
    brand: str
    manufacturer: str
    competitor_group: str
    estimated_market_value: float = Field(ge=0)
    estimated_market_volume: float = Field(ge=0)
    market_share_pct: float = Field(ge=0, le=100)
    market_growth_pct: float = Field(ge=-100, le=200)
    avg_market_price: float = Field(ge=0)
    promo_intensity_index: float = Field(ge=0, le=100)
    distribution_coverage_pct: float = Field(ge=0, le=100)
    digital_visibility_index: float = Field(ge=0, le=100)
    competitive_pressure_index: float = Field(ge=0, le=100)
    opportunity_score: float = Field(ge=0, le=100)
    opportunity_components: OpportunityComponents
    price_anchor_source: Literal["serper_snapshot", "synthetic_fallback"]
    price_anchor_method: Literal["median_normalized_unit_price", "median_observed_price", "deterministic_synthetic"]
    price_anchor_value: float | None = Field(default=None, ge=0)
    source_type: Literal["synthetic_calibrated"] = "synthetic_calibrated"
    data_confidence: Literal["calibrated"] = "calibrated"
    generated_at: datetime


class MarketIntent(FrozenModel):
    analysis_type: Literal["position", "competitors", "pricing", "growth", "share", "distribution", "pressure", "opportunity", "sales_pressure"]
    period: date
    product_name: str | None = None
    region_name: str | None = None
    category: str | None = None


class MarketResult(FrozenModel):
    status: Literal["ok", "EXTERNAL_MARKET_SIGNAL_NOT_AVAILABLE", "MARKET_DATA_NOT_AVAILABLE"]
    analysis_type: str
    requested_product: str | None = None
    requested_region: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    internal_sales_evidence: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SnapshotCollectionReport(FrozenModel):
    queries_sent: int
    normalized_results: int
    products_observed: list[str]
    missing_products: list[str]
    failures: list[str]
    snapshot_at: datetime
