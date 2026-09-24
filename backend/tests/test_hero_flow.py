import pytest

from app.core.schemas import ChatRequest
from app.ossie import graph_nodes as ossie_graph_nodes
from app.services.chat import run_chat


class _FakeOssieRegistry:
    dataset_fields = {"monthly_executive": {"calmonth": {}}}


class _FakeOssieService:
    registry = _FakeOssieRegistry()

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
        return self.resolve(question)

    def execute_query(self, request, trace_id=""):
        return {
            "sql": "SELECT calmonth, SUM(bill_val) FROM gold.view GROUP BY calmonth",
            "rows": [{"calmonth": 202410, "metric_value": 100.0}, {"calmonth": 202411, "metric_value": 90.0}],
            "semantic_plan": {"source_view": "gold.rpt_sap_monthly_executive_semantic", "grain": "calmonth"},
            "telemetry": {"data_backend": "impala", "success": True},
        }


@pytest.mark.asyncio
async def test_hero_question_returns_structured_answer(monkeypatch):
    # Default config is OSSIE + Impala; the Impala call itself is faked here
    # so this stays a pure workflow-shape test, not an integration test.
    monkeypatch.setattr(ossie_graph_nodes, "get_tempo_ossie_service", lambda: _FakeOssieService())
    response = await run_chat(ChatRequest(question="Bagaimana tren Gross Sales selama Q4?"))
    assert response.status == "ok"
    assert response.answer.summary
    assert response.metadata.intent == "ossie_analytical"
    assert response.metadata.session_id == "demo-session"
    assert response.data.rows
    assert response.chart_spec is None or response.chart_spec.type in {"bar", "line", "table"}
    assert "stockout" not in response.answer.summary.lower()
