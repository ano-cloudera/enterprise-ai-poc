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


def test_ossie_analytical_returns_governed_evidence(monkeypatch) -> None:
    monkeypatch.setattr(graph_nodes, "get_tempo_ossie_service", lambda: _FakeService())
    result = graph_nodes.ossie_analytical(
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

