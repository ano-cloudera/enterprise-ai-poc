from __future__ import annotations

import pytest

from app.graph import nodes
from app.ossie import graph_nodes


@pytest.mark.asyncio
async def test_ossie_mode_routes_greeting_and_analysis_without_legacy_resolution(
    monkeypatch,
) -> None:
    monkeypatch.setattr(nodes.settings, "semantic_execution_mode", "ossie")
    greeting = await nodes.route_intent({"question": "Halo", "language": "id"})
    analytical = await nodes.route_intent(
        {"question": "Berapa Gross Sales Q4?", "language": "id"}
    )
    forecast = await nodes.route_intent(
        {"question": "Forecast Januari 2025", "language": "id"}
    )
    assert greeting["intent"] == "ossie_conversational"
    assert analytical["intent"] == "ossie_analytical"
    assert forecast["intent"] == "ossie_analytical"


def test_ossie_conversational_first_turn_shows_the_full_greeting_in_indonesian() -> None:
    result = graph_nodes.ossie_conversational(
        {"question": "Halo", "language": "id", "dashboard_state": {}}
    )
    assert result["status"] == "ok"
    assert "Halo, saya SCAN" in result["answer"]["summary"]
    assert "Oktober" in result["answer"]["summary"]
    # The 4 fixed sample questions requested by the user, verbatim.
    assert result["answer"]["recommended_actions"] == [
        "Bagaimana tren Gross Sales selama Q4?",
        "Material mana dengan Fill Rate terendah?",
        "Bagaimana perbandingan Sell-In dan Sell-Out?",
        "Sales office mana dengan picking delay tertinggi?",
    ]


def test_ossie_conversational_first_turn_shows_the_full_greeting_in_english() -> None:
    result = graph_nodes.ossie_conversational(
        {"question": "Hello", "language": "en", "dashboard_state": {}}
    )
    assert "Hello, I'm SCAN" in result["answer"]["summary"]
    assert len(result["answer"]["recommended_actions"]) == 4


def test_ossie_conversational_later_turn_does_not_repeat_the_full_greeting() -> None:
    # state["history"] non-empty signals this isn't the first message in the
    # session - a later "halo" should get a short reply, not the full pitch
    # with the 4 sample questions again.
    result = graph_nodes.ossie_conversational({
        "question": "Halo",
        "language": "id",
        "dashboard_state": {},
        "history": [{"role": "user", "content": "Berapa Gross Sales Q4?"}],
    })
    assert result["status"] == "ok"
    assert "Halo, saya SCAN" not in result["answer"]["summary"]
    assert result["answer"]["recommended_actions"] == []


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Halo", "id"),
        ("Hai", "id"),
        ("Hello", "en"),
        ("Hi", "en"),
        # Longer, keyword-less sentences - not covered by any fixed marker
        # list, only detectable via actual language identification.
        ("Bisakah Anda menjelaskan lebih detail mengenai hal ini", "id"),
        ("Could you explain this in more detail please", "en"),
    ],
)
def test_language_detection_handles_short_greetings_and_keyword_less_sentences(question, expected) -> None:
    assert graph_nodes._language(question) == expected


class _FakeRegistry:
    dataset_fields = {"monthly_executive": {"calmonth": {}}}


class _FakeService:
    registry = _FakeRegistry()

    def resolve(self, _question):
        return {
            "status": "resolved",
            "metric": "gross_billing_value",
            "definition": {
                "description": "Official Gross Billing Value",
                "metric_id": "SI-01",
                "allowed_dimensions": ["calmonth"],
                "base_dataset": "monthly_executive",
                "business_approval_status": "pending_business_confirmation",
                "governance_status": "approved_candidate",
                "ai_context": {},
            },
        }

    async def resolve_with_llm_fallback(self, question, *, trace_id=""):
        # The deterministic path already resolves in this fixture, so the
        # LLM fallback is never reached - mirrors resolve()'s result.
        return self.resolve(question)

    def execute_query(self, request, trace_id=""):
        assert request.metric == "gross_billing_value"
        assert request.dimensions == ["calmonth"]
        assert request.start_calmonth == 202410
        assert request.end_calmonth == 202412
        return {
            "sql": "SELECT calmonth, SUM(sales_bill_val) FROM gold.view GROUP BY calmonth",
            "rows": [
                {"calmonth": 202410, "metric_value": 100.0},
                {"calmonth": 202411, "metric_value": 90.0},
            ],
            "semantic_plan": {
                "source_view": "gold.rpt_sap_monthly_executive_semantic",
                "grain": "calmonth",
            },
            "telemetry": {"data_backend": "impala", "success": True},
        }


@pytest.mark.asyncio
async def test_ossie_analytical_returns_governed_evidence(monkeypatch) -> None:
    monkeypatch.setattr(graph_nodes, "get_tempo_ossie_service", lambda: _FakeService())
    result = await graph_nodes.ossie_analytical(
        {
            "question": "Tampilkan Gross Sales per bulan",
            "language": "id",
            "dashboard_state": {},
            "trace_id": "test",
        }
    )
    assert result["status"] == "ok"
    assert len(result["rows"]) == 2
    assert result["chart_spec"]["type"] == "line"
    assert result["ui_actions"][0]["type"] == "SHOW_TABLE"
    assert any("pending TEMPO" in caveat for caveat in result["answer"]["caveats"])


@pytest.mark.asyncio
async def test_ossie_analytical_uses_llm_narrative_when_available(monkeypatch) -> None:
    # Verifies the LLM narrative path actually replaces the deterministic
    # template summary/drivers, while still keeping the deterministic
    # Metric/Source/Grain drivers and governance caveats prepended so the
    # checkable evidence isn't lost just because the LLM wrote the prose.
    from app.llm.models import AnalysisResult, ModelTelemetry, StructuredAnalysis, AnalysisDriver

    monkeypatch.setattr(graph_nodes, "get_tempo_ossie_service", lambda: _FakeService())

    class _FakeNarrativeProvider:
        async def generate_structured(self, payload, *, language, trace_id):
            assert payload.query_result["rows"]  # got real governed rows, not empty
            return AnalysisResult(
                analysis=StructuredAnalysis(
                    summary="Gross Sales Tempo turun tipis di November dibanding Oktober.",
                    drivers=[AnalysisDriver(title="Tren bulanan", description="Penurunan kecil dari Rp100 ke Rp90.", evidence="calmonth=202411; metric_value=90.0")],
                    recommended_actions=[],
                    caveats=[],
                ),
                telemetry=ModelTelemetry(trace_id=trace_id, provider="fake", model="fake", latency_ms=1, retry_count=0, success=True, structured_validation_success=True),
            )

    monkeypatch.setattr(graph_nodes, "get_llm_provider", lambda: _FakeNarrativeProvider())
    result = await graph_nodes.ossie_analytical(
        {
            "question": "Tampilkan Gross Sales per bulan",
            "language": "id",
            "dashboard_state": {},
            "trace_id": "test",
        }
    )
    assert result["answer"]["summary"] == "Gross Sales Tempo turun tipis di November dibanding Oktober."
    assert any(driver.startswith("Metric: SI-01") for driver in result["answer"]["drivers"])
    assert any("Tren bulanan" in driver for driver in result["answer"]["drivers"])
    assert any("pending TEMPO" in caveat for caveat in result["answer"]["caveats"])


@pytest.mark.asyncio
async def test_ossie_analytical_falls_back_to_deterministic_summary_on_llm_failure(monkeypatch) -> None:
    from app.llm.providers import LLMProviderError

    monkeypatch.setattr(graph_nodes, "get_tempo_ossie_service", lambda: _FakeService())

    class _FailingProvider:
        async def generate_structured(self, payload, *, language, trace_id):
            raise LLMProviderError("unavailable")

    monkeypatch.setattr(graph_nodes, "get_llm_provider", lambda: _FailingProvider())
    result = await graph_nodes.ossie_analytical(
        {
            "question": "Tampilkan Gross Sales per bulan",
            "language": "id",
            "dashboard_state": {},
            "trace_id": "test",
        }
    )
    # Falls back to the deterministic template rather than failing the request.
    assert result["status"] == "ok"
    assert "Official Gross Billing Value" in result["answer"]["summary"]
    assert any("pending TEMPO" in caveat for caveat in result["answer"]["caveats"])

