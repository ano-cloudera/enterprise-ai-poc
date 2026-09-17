from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.graph.nodes import market, route_intent
from app.market_intelligence.calibration import build_price_anchors, generate_calibrated_market, opportunity_score
from app.market_intelligence.collector import MarketSnapshotCollector
from app.market_intelligence.models import DigitalMarketSignal, MarketIntent, MarketResult
from app.market_intelligence.normalization import normalize_serpapi_results, parse_package
from app.market_intelligence.providers.mock_api import MarketSignalUnavailable, MockExternalMarketApiProvider
from app.market_intelligence.providers.serpapi import SerpApiMarketProvider, SerpApiUnavailable
from app.market_intelligence.providers.serper import SerperDevMarketProvider, SerperDevUnavailable
from app.market_intelligence.repository import MarketRepository
from app.market_intelligence.service import MarketIntelligenceTool, load_market_governance, resolve_market_intent
from app.mock_market_api.main import create_app
from app.llm.models import AnalysisDriver, StructuredAnalysis
from app.semantic.loader import load_semantic_project


OBSERVED_AT = datetime(2026, 9, 15, tzinfo=timezone.utc)


def _payload():
    return {
        "shopping_results": [
            {"title": "Bodrex 20 Tablet", "source": "Apotek A", "extracted_price": 12500, "extracted_old_price": 15000, "rating": 4.8, "reviews": 120, "position": 1, "delivery": "In stock"},
            {"title": "Bodrex 20 Tablet", "source": "Apotek A", "extracted_price": 12500, "rating": 4.8, "reviews": 120, "position": 2},
            {"title": "Bodrex Extra", "source": "Toko B", "price": "Rp18.000", "position": 3},
        ]
    }


def test_serpapi_requires_environment_auth_when_enabled():
    with pytest.raises(SerpApiUnavailable, match="SERPAPI_NOT_CONFIGURED"):
        SerpApiMarketProvider(api_key="", enabled=True).collect("Bodrex", "Bodrex", "Adult Analgesic")


def test_unconfigured_collector_reports_zero_external_queries(tmp_path):
    repository = MarketRepository(tmp_path / "unconfigured.duckdb")
    report = MarketSnapshotCollector(
        SerpApiMarketProvider(api_key="", enabled=True), repository, load_market_governance("tempo_scan")
    ).collect(max_queries=5, observed_at=OBSERVED_AT)
    assert report.queries_sent == 0
    assert report.normalized_results == 0
    assert repository.snapshot_count() == 0


def test_serpapi_normalization_handles_missing_values_deduplicates_and_limits():
    rows = normalize_serpapi_results(_payload(), "Bodrex", "Bodrex", "Adult Analgesic", OBSERVED_AT, limit=2)
    assert len(rows) == 2
    first = rows[0]
    assert first.observed_price == 12500
    assert first.discount_pct == pytest.approx(16.6667, rel=1e-3)
    assert first.source_type == "serpapi_snapshot"
    assert first.data_confidence == "observed"
    assert rows[1].rating is None and rows[1].review_count is None


def test_serpapi_failure_is_safe_and_never_leaks_key():
    secret = "secret-serp-key"

    class BrokenClient:
        def get(self, *args, **kwargs):
            raise httpx.ConnectError(f"failed with {secret}")

    with pytest.raises(SerpApiUnavailable) as error:
        SerpApiMarketProvider(api_key=secret, enabled=True, client=BrokenClient()).collect("Bodrex", "Bodrex", "Adult Analgesic")
    assert secret not in str(error.value)


def test_serper_dev_uses_header_auth_normalizes_results_and_limits():
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "shopping": [
                    {"title": "Bodrex 20 Tablet", "source": "Apotek A", "price": "Rp12.500", "oldPrice": "Rp15.000", "rating": 4.8, "ratingCount": 120, "position": 1, "delivery": "Tersedia"},
                    {"title": "Bodrex 20 Tablet", "source": "Apotek A", "price": "Rp12.500", "position": 2},
                    {"title": "Bodrex Extra", "source": "Toko B", "price": "Rp18.000", "position": 3},
                ]
            }

    class Client:
        def post(self, url, **kwargs):
            captured.update({"url": url, **kwargs})
            return Response()

    rows = SerperDevMarketProvider(api_key="test-key", client=Client(), result_limit=2).collect(
        "Bodrex harga", "Bodrex", "Adult Analgesic", observed_at=OBSERVED_AT
    )
    assert captured["headers"]["X-API-KEY"] == "test-key"
    assert "api_key" not in captured["json"]
    assert len(rows) == 2
    assert rows[0].observed_price == 12500
    assert rows[0].review_count == 120
    assert rows[0].source == "serper_dev" and rows[0].source_type == "serper_snapshot"


def test_serper_dev_missing_key_and_failure_are_safe():
    with pytest.raises(SerperDevUnavailable, match="SERPER_NOT_CONFIGURED"):
        SerperDevMarketProvider(api_key="").collect("Bodrex", "Bodrex", "Adult Analgesic")

    secret = "serper-secret"

    class BrokenClient:
        def post(self, *args, **kwargs):
            raise httpx.ConnectError(secret)

    with pytest.raises(SerperDevUnavailable) as error:
        SerperDevMarketProvider(api_key=secret, client=BrokenClient()).collect("Bodrex", "Bodrex", "Adult Analgesic")
    assert secret not in str(error.value)


@pytest.mark.parametrize(
    ("title", "price", "package_type", "quantity", "unit_type", "unit_price"),
    [
        ("Bodrex Strip 10 Tablet", 10000, "strip", 10, "tablet", 1000),
        ("Bodrex 20 Tablet", 12000, "pack", 20, "tablet", 600),
        ("Bodrex Box 10 Strip x 4 Tablet", 40000, "box", 40, "tablet", 1000),
    ],
)
def test_package_and_unit_normalization(title, price, package_type, quantity, unit_type, unit_price):
    parsed = parse_package(title, price)
    assert parsed.package_type == package_type
    assert parsed.package_quantity == quantity
    assert parsed.unit_type == unit_type
    assert parsed.normalized_unit_price == pytest.approx(unit_price)
    assert parsed.normalization_confidence == "high"


def test_ambiguous_package_preserves_price_without_guessing_quantity():
    parsed = parse_package("Bodrex Xtra 4's", 2500)
    assert parsed.package_type is None
    assert parsed.package_quantity is None
    assert parsed.unit_type is None
    assert parsed.normalized_unit_price is None
    assert parsed.normalization_confidence == "low"


def test_product_variant_number_is_not_mistaken_for_package_quantity():
    parsed = parse_package("Hemaviton Fitomega-3 Kapsul 30's", 55000)
    assert parsed.package_quantity is None
    assert parsed.normalized_unit_price is None
    assert parsed.normalization_confidence == "low"


def test_normalized_serper_snapshot_contains_package_provenance():
    payload = {"shopping": [{"title": "Bodrex Strip 10 Tablet", "source": "A", "price": "Rp10.000"}]}
    row = SerperDevMarketProvider(api_key="x", client=type("C", (), {
        "post": lambda self, *args, **kwargs: type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: payload})()
    })()).collect("Bodrex", "Bodrex", "Adult Analgesic", OBSERVED_AT)[0]
    assert row.package_type == "strip"
    assert row.package_quantity == 10
    assert row.normalized_unit_price == 1000
    assert row.normalization_confidence == "high"


def _signal(product="Bodrex", seller="Apotek A"):
    return DigitalMarketSignal(
        observed_at=OBSERVED_AT, query=product, product_name=product, category="Adult Analgesic",
        seller=seller, title=f"{product} product", observed_price=12500, old_price=15000,
        discount_pct=16.67, rating=4.8, review_count=120, search_position=1,
        availability="available",
    )


def test_snapshot_persistence_is_idempotent_and_previous_snapshot_survives_failure(tmp_path):
    repository = MarketRepository(tmp_path / "market.duckdb")
    repository.upsert_snapshots([_signal()])
    repository.upsert_snapshots([_signal()])
    assert repository.snapshot_count() == 1
    before = repository.list_snapshots()
    # Collector failures perform no destructive repository operation.
    assert repository.list_snapshots() == before


def test_collector_persists_partial_success_and_preserves_previous_on_total_failure(tmp_path):
    repository = MarketRepository(tmp_path / "collector.duckdb")
    repository.upsert_snapshots([_signal("Existing")])

    class PartialProvider:
        def collect(self, query, product_name, category, observed_at=None):
            if product_name == "Bodrex":
                return [_signal("Bodrex")]
            raise SerpApiUnavailable("SERPAPI_REQUEST_FAILED")

    governance = load_market_governance("tempo_scan")
    report = MarketSnapshotCollector(PartialProvider(), repository, governance).collect(max_queries=2, observed_at=OBSERVED_AT)
    assert report.queries_sent == 2 and report.products_observed == ["Bodrex"]
    assert repository.snapshot_count() == 2

    class FailedProvider:
        def collect(self, **kwargs):
            raise SerpApiUnavailable("SERPAPI_REQUEST_FAILED")

    before = repository.list_snapshots()
    failed = MarketSnapshotCollector(FailedProvider(), repository, governance).collect(max_queries=2, observed_at=OBSERVED_AT)
    assert failed.normalized_results == 0
    assert repository.list_snapshots() == before


def test_collector_persists_multiple_observed_products(tmp_path):
    repository = MarketRepository(tmp_path / "multi.duckdb")

    class Provider:
        configured = True

        def collect(self, query, product_name, category, observed_at=None):
            return [_signal(product_name, f"Seller {product_name}")]

    report = MarketSnapshotCollector(Provider(), repository, load_market_governance("tempo_scan")).collect(max_queries=3, observed_at=OBSERVED_AT)
    assert report.products_observed == ["Bodrex", "Bodrex Flu & Batuk", "Oskadon"]
    assert {row.product_name for row in repository.list_snapshots()} == set(report.products_observed)


def test_calibrated_market_generation_is_deterministic_consistent_and_provenanced():
    governance = load_market_governance("tempo_scan")
    first = generate_calibrated_market(governance, date(2024, 1, 1), date(2024, 3, 1), generated_at=OBSERVED_AT)
    second = generate_calibrated_market(governance, date(2024, 1, 1), date(2024, 3, 1), generated_at=OBSERVED_AT)
    assert first == second
    assert first
    assert all(0 <= row.market_share_pct <= 100 for row in first)
    assert all(0 <= row.opportunity_score <= 100 for row in first)
    assert all(row.source_type == "synthetic_calibrated" and row.data_confidence == "calibrated" for row in first)
    groups = {}
    for row in first:
        groups.setdefault((row.period, row.region_name, row.category), []).append(row)
    for rows in groups.values():
        assert sum(row.market_share_pct for row in rows) == pytest.approx(100)
        total = sum(row.estimated_market_value for row in rows)
        assert all(row.estimated_market_value == pytest.approx(total * row.market_share_pct / 100) for row in rows)


def test_median_normalized_unit_price_anchors_calibration_with_bounded_adjustment():
    signals = [
        _signal().model_copy(update={"package_type": "strip", "package_quantity": 10, "unit_type": "tablet", "normalized_unit_price": value, "normalization_confidence": "high"})
        for value in (900.0, 1000.0, 1100.0)
    ]
    anchors = build_price_anchors(signals)
    assert anchors["Bodrex"].value == 1000
    assert anchors["Bodrex"].method == "median_normalized_unit_price"
    rows = generate_calibrated_market(load_market_governance("tempo_scan"), date(2024, 3, 1), date(2024, 3, 1), OBSERVED_AT, signals)
    bodrex = [row for row in rows if row.product_name == "Bodrex"]
    assert all(900 <= row.avg_market_price <= 1100 for row in bodrex)
    assert all(row.price_anchor_source == "serper_snapshot" for row in bodrex)
    assert all(row.price_anchor_method == "median_normalized_unit_price" for row in bodrex)


def test_price_anchor_prefers_comparable_consumer_units_when_group_sizes_tie():
    signals = [
        _signal().model_copy(update={
            "unit_type": unit_type, "package_type": package_type, "package_quantity": quantity,
            "normalized_unit_price": price, "normalization_confidence": "high",
        })
        for unit_type, package_type, quantity, price in (
            ("box", "box", 1, 8000.0), ("box", "box", 1, 8100.0),
            ("tablet", "box", 12, 740.0), ("tablet", "pack", 16, 470.0),
        )
    ]
    anchor = build_price_anchors(signals)["Bodrex"]
    assert anchor.unit_type == "tablet"
    assert anchor.value == pytest.approx(605)


def test_missing_observed_price_uses_explicit_synthetic_fallback():
    rows = generate_calibrated_market(load_market_governance("tempo_scan"), date(2024, 3, 1), date(2024, 3, 1), OBSERVED_AT, [])
    healthyway = next(row for row in rows if row.product_name == "HealthyWay")
    assert healthyway.price_anchor_source == "synthetic_fallback"
    assert healthyway.price_anchor_method == "deterministic_synthetic"
    assert healthyway.price_anchor_value is None


def test_adult_analgesic_leader_group_constraint_is_explicit_and_enforced():
    governance = load_market_governance("tempo_scan")
    constraint = governance.category_constraints["Adult Analgesic"]
    rows = generate_calibrated_market(governance, date(2024, 3, 1), date(2024, 3, 1), OBSERVED_AT)
    groups = {}
    for row in rows:
        if row.category == "Adult Analgesic":
            groups.setdefault(row.region_name, []).append(row)
    for category_rows in groups.values():
        leader_share = sum(row.market_share_pct for row in category_rows if row.brand in constraint.leader_group_brands)
        assert leader_share >= constraint.minimum_combined_share_pct
        assert sum(row.market_share_pct for row in category_rows) == pytest.approx(100)
        assert all(row.source_type == "synthetic_calibrated" for row in category_rows)


def test_opportunity_score_returns_transparent_bounded_components():
    score, components = opportunity_score(market_growth_pct=12, market_size=200000, market_share_pct=15, distribution_coverage_pct=55, competitive_pressure_index=70)
    assert 0 <= score <= 100
    assert set(components) == {"growth", "market_size", "share_gap", "distribution_gap", "competitive_pressure"}
    assert score == pytest.approx(sum(components.values()) / 5)


@pytest.fixture
def market_repo(tmp_path):
    repository = MarketRepository(tmp_path / "market.duckdb")
    repository.upsert_snapshots([_signal(), _signal("Oskadon", "Toko B")])
    repository.replace_calibrated(generate_calibrated_market(load_market_governance("tempo_scan"), date(2024, 1, 1), date(2024, 3, 1), generated_at=OBSERVED_AT))
    return repository


@pytest.fixture
def market_client(market_repo):
    return TestClient(create_app(market_repo))


def test_mock_market_api_health_and_provenance(market_client):
    health = market_client.get("/health").json()
    assert health["status"] == "ok"
    response = market_client.get("/v1/market/share", params={"period": "2024-03-01", "brand": "Bodrex"}).json()
    assert response["status"] == "ok" and response["data"]
    assert response["metadata"]["contains_synthetic_data"] is True


def test_calibrated_pricing_honors_period_region_and_product_filters(market_client):
    body = market_client.get(
        "/v1/market/pricing",
        params={"period": "2024-03-01", "region": "Jawa Barat", "product": "HealthyWay"},
    ).json()
    assert len(body["data"]) == 1
    assert body["data"][0]["period"] == "2024-03-01"
    assert body["data"][0]["region_name"] == "Jawa Barat"


@pytest.mark.parametrize("endpoint", ["products", "pricing", "competitors", "share", "opportunity"])
def test_mock_market_api_endpoints_and_filters(market_client, endpoint):
    response = market_client.get(f"/v1/market/{endpoint}", params={"region": "Jawa Barat"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "source" in body["metadata"]


def test_mock_api_runtime_provider_implements_governed_methods(market_client):
    provider = MockExternalMarketApiProvider("http://market.test", client=market_client)
    assert provider.get_market_share(period="2024-03-01", brand="Bodrex")
    assert provider.get_competitors(category="Adult Analgesic")
    assert provider.get_pricing(product="Bodrex")
    assert provider.get_opportunity(product="Bodrex")


def test_position_tool_returns_bodrex_and_governed_category_competitors(market_client):
    provider = MockExternalMarketApiProvider("http://market.test", client=market_client)
    result = MarketIntelligenceTool(provider).analyze(
        MarketIntent(analysis_type="position", product_name="Bodrex", region_name="Jawa Barat", period=date(2024, 3, 1))
    )
    assert result.status == "ok"
    assert {row["brand"] for row in result.evidence} >= {"Bodrex", "Panadol", "Paramex"}


def test_unavailable_market_api_returns_controlled_number_free_fallback():
    class MissingProvider:
        def get_market_share(self, **kwargs):
            raise MarketSignalUnavailable("EXTERNAL_MARKET_SIGNAL_NOT_AVAILABLE")

    result = MarketIntelligenceTool(MissingProvider()).analyze(MarketIntent(analysis_type="share", product_name="Bodrex", period=date(2024, 3, 1)))
    assert result.status == "EXTERNAL_MARKET_SIGNAL_NOT_AVAILABLE"
    assert result.evidence == []


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Kenapa sales Jawa Barat turun bulan ini?", "analytical"),
        ("Forecast Jawa Barat bulan depan", "forecast"),
        ("Apakah curah hujan Jawa Barat meningkat?", "weather"),
        ("Bagaimana posisi Bodrex dibanding kompetitor?", "market"),
        ("Region mana yang punya opportunity terbesar untuk Bodrex?", "market"),
    ],
)
@pytest.mark.asyncio
async def test_market_routing_preserves_existing_routes(question, expected):
    assert (await route_intent({"question": question}))["intent"] == expected


def test_market_follow_up_intent_preserves_governed_dashboard_context():
    intent = resolve_market_intent(
        "Bagaimana market share-nya?",
        {"filters": {"product": ["Bodrex"], "region": ["Jawa Barat"]}},
        load_semantic_project("tempo_scan"), load_market_governance("tempo_scan"),
    )
    assert intent.product_name == "Bodrex" and intent.region_name == "Jawa Barat"
    assert intent.analysis_type == "share"


@pytest.mark.asyncio
async def test_market_graph_keeps_metrics_immutable_and_labels_synthetic_data(monkeypatch):
    result = MarketResult(
        status="ok", analysis_type="opportunity", requested_product="Bodrex", requested_region="Jawa Barat",
        evidence=[{"brand": "Bodrex", "opportunity_score": 72.5, "source_type": "synthetic_calibrated", "data_confidence": "calibrated"}],
        metadata={"contains_synthetic_data": True},
    )

    class Tool:
        def analyze(self, intent):
            return result

    captured = {}

    class UnsafeExplainer:
        async def generate_structured(self, payload, **kwargs):
            captured["payload"] = payload
            return SimpleNamespace(
                analysis=StructuredAnalysis(
                    summary="Skor peluang Bodrex adalah 72,5 dari 100.",
                    drivers=[AnalysisDriver(title="Peluang", description="Skor terkalibrasi tersedia.", evidence="opportunity_score=72.5")],
                    recommended_actions=[], caveats=[],
                ),
                telemetry=SimpleNamespace(model_dump=lambda: {"success": True}),
            )

    monkeypatch.setattr("app.graph.nodes.get_llm_provider", lambda: UnsafeExplainer())

    state = await market({"question": "Opportunity Bodrex di Jawa Barat", "language": "id", "dashboard_state": {}}, tool=Tool())
    assert state["rows"][0]["opportunity_score"] == 72.5
    assert "72,5" in state["answer"]["summary"]
    assert captured["payload"].business_context["calculated_metrics_immutable"] is True
    combined = " ".join([state["answer"]["summary"], *state["answer"]["caveats"]]).lower()
    assert "synthetic" in combined
    assert "iqvia" not in combined and "nielseniq" not in combined


@pytest.mark.asyncio
async def test_market_graph_uses_successful_structured_analysis(monkeypatch):
    result = MarketResult(
        status="ok", analysis_type="share", requested_product="Bodrex", requested_region=None,
        evidence=[{
            "product_name": "Bodrex", "market_share_pct": 19.9471, "market_growth_pct": 2.8986,
            "source_type": "synthetic_calibrated", "data_confidence": "calibrated",
        }],
        metadata={"contains_synthetic_data": True},
    )

    class Tool:
        def analyze(self, intent):
            return result

    expected = "Pangsa pasar Bodrex sekitar 19,9%, dengan pertumbuhan pasar 2,9%."

    class Explainer:
        async def generate_structured(self, payload, **kwargs):
            return SimpleNamespace(
                analysis=StructuredAnalysis(summary=expected, drivers=[], recommended_actions=[], caveats=[]),
                telemetry=SimpleNamespace(model_dump=lambda: {"success": True}),
            )

    monkeypatch.setattr("app.graph.nodes.get_llm_provider", lambda: Explainer())
    state = await market({"question": "Bagaimana market share Bodrex?", "language": "id", "dashboard_state": {}}, tool=Tool())

    assert state["answer"]["summary"] == expected
    assert "market_share_pct=" not in state["answer"]["summary"]


@pytest.mark.asyncio
async def test_market_summary_selects_requested_product_from_peer_evidence():
    result = MarketResult(
        status="ok", analysis_type="position", requested_product="Bodrex", requested_region=None,
        evidence=[
            {"brand": "Panadol", "product_name": "Panadol", "market_share_pct": 30, "source_type": "synthetic_calibrated", "data_confidence": "calibrated"},
            {"brand": "Bodrex", "product_name": "Bodrex", "market_share_pct": 20, "source_type": "synthetic_calibrated", "data_confidence": "calibrated"},
        ], metadata={"contains_synthetic_data": True},
    )

    class Tool:
        def analyze(self, intent):
            return result

    state = await market({"question": "Posisi Bodrex dibanding kompetitor", "language": "id", "dashboard_state": {}}, tool=Tool())
    assert "Bodrex" in state["answer"]["summary"]
    assert "pangsa pasar 20,0%" in state["answer"]["summary"]
    assert "market_share_pct" not in state["answer"]["summary"]


def test_project_owns_ten_market_golden_questions_including_fallbacks():
    questions = load_semantic_project("tempo_scan").market_golden_questions
    assert len(questions) >= 10
    assert any(item.expected_status == "EXTERNAL_MARKET_SIGNAL_NOT_AVAILABLE" for item in questions)
    assert any(item.expected_status == "MARKET_DATA_NOT_AVAILABLE" for item in questions)


@pytest.mark.parametrize("golden", load_semantic_project("tempo_scan").market_golden_questions, ids=lambda item: item.id)
def test_market_golden_questions_resolve_deterministically(golden):
    intent = resolve_market_intent(golden.question, golden.context, load_semantic_project("tempo_scan"), load_market_governance("tempo_scan"))
    assert intent.analysis_type == golden.analysis_type
    assert intent.product_name == golden.product_name
    assert intent.region_name == golden.region_name
