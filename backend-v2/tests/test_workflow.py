from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.models import AnalysisOutput, AskDataRequest, QueryPlan
from app.graph.workflow import WorkflowDependencies, build_workflow
from app.sql.validator import ValidatedSQL


class FakeProvider:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    async def generate_structured(self, messages, response_model, **kwargs):
        self.calls.append(response_model.__name__)
        return response_model.model_validate(self.responses.pop(0))


class FakeRegistry:
    def __init__(self, provider: FakeProvider) -> None:
        self.provider = provider

    def resolve(self, provider: str, model: str):
        return self.provider


class FakeContext:
    def __init__(self, resolution: dict, sql: str = "SELECT d.material FROM gold.allowed d LIMIT 10") -> None:
        self.resolution = resolution
        self.sql = sql

    def resolve(self, question: str):
        return self.resolution

    def planner_context(self, domains=None):
        return {"datasets": [{"view": "gold.allowed", "columns": ["material", "value"]}]}

    def compile_governed(self, metric: str, question: str):
        return self.sql


class FakeExecutor:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.queries: list[str] = []

    def execute(self, sql: str, request_id: str):
        self.queries.append(sql)
        return {"columns": list(self.rows[0]) if self.rows else [], "rows": self.rows, "row_count": len(self.rows), "execution_ms": 4}


@dataclass
class FakeValidationContext:
    pass


def analysis(chart_spec=None):
    return {
        "direct_answer": "Jawaban grounded",
        "executive_summary": "Ringkasan",
        "insights": ["Insight"],
        "business_implications": ["Implikasi"],
        "caveats": [],
        "data_reference": "actual query result",
        "chart_spec": chart_spec,
    }


def deps(context, provider, rows, validator=lambda sql, context: ValidatedSQL(True, sql=sql)):
    return WorkflowDependencies(
        semantic_context=context,
        provider_registry=FakeRegistry(provider),
        query_executor=FakeExecutor(rows),
        sql_validator=validator,
        validation_context=FakeValidationContext(),
    )


@pytest.mark.asyncio
async def test_governed_path_uses_deterministic_plan_and_grounded_analysis() -> None:
    provider = FakeProvider([analysis({"type": "bar", "title": "By material", "x": "material", "y": "value"})])
    context = FakeContext({"status": "resolved", "metric": "material_sell_in_value", "definition": {"base_dataset": "material_360"}})
    dependencies = deps(context, provider, [{"material": "A", "value": 10}])

    state = await build_workflow(dependencies).ainvoke(AskDataRequest(session_id="s1", question="top material", provider="qwen", model="qwen-model").model_dump())

    assert state["status"] == "SUCCESS"
    assert state["strategy"] == "governed"
    assert provider.calls == ["AnalysisOutput"]
    assert state["chart_spec"]["x"] == "material"
    assert state["timings"]["validation_ms"] >= 0


@pytest.mark.asyncio
async def test_controlled_fallback_uses_exactly_planner_then_analyst() -> None:
    provider = FakeProvider([
        {"strategy": "sql_fallback", "domains": ["sales"], "metrics": [], "dimensions": ["material"], "filters": {}, "analysis_type": "ranking", "sql": "SELECT d.material, d.value FROM gold.allowed d LIMIT 10", "clarification_question": None},
        analysis(),
    ])
    dependencies = deps(FakeContext({"status": "unsupported"}), provider, [{"material": "A", "value": 10}])

    state = await build_workflow(dependencies).ainvoke(AskDataRequest(session_id="s1", question="fallback", provider="gemini", model="gemini-model").model_dump())

    assert state["status"] == "SUCCESS"
    assert state["strategy"] == "sql_fallback"
    assert provider.calls == ["QueryPlan", "AnalysisOutput"]


@pytest.mark.asyncio
async def test_dimension_mismatch_routes_to_controlled_planner() -> None:
    provider = FakeProvider([
        {"strategy": "sql_fallback", "domains": ["sales"], "metrics": ["material_sell_in_value"], "dimensions": ["material"], "filters": {}, "analysis_type": "ranking", "sql": "SELECT d.material, d.value FROM gold.allowed d LIMIT 10", "clarification_question": None},
        analysis(),
    ])
    context = FakeContext({
        "status": "resolved",
        "metric": "gross_billing_value",
        "definition": {"base_dataset": "monthly_executive"},
        "dimension_mismatch": ["material"],
    })

    state = await build_workflow(deps(context, provider, [{"material": "A", "value": 10}])).ainvoke(
        AskDataRequest(session_id="s1", question="Sell-In per material", provider="qwen", model="qwen-model").model_dump()
    )

    assert state["strategy"] == "sql_fallback"
    assert provider.calls == ["QueryPlan", "AnalysisOutput"]


@pytest.mark.asyncio
async def test_clarification_and_unsupported_do_not_execute_query() -> None:
    clarification_provider = FakeProvider([])
    clarification = deps(FakeContext({"status": "needs_clarification", "question": "Sell-In atau Sell-Out?", "options": []}), clarification_provider, [])
    state = await build_workflow(clarification).ainvoke(AskDataRequest(session_id="s", question="total sales", provider="qwen", model="m").model_dump())
    assert state["status"] == "CLARIFICATION"
    assert state["answer"]["direct_answer"] == "Sell-In atau Sell-Out?"
    assert clarification.query_executor.queries == []

    unsupported_provider = FakeProvider([{"strategy": "unsupported", "domains": [], "metrics": [], "dimensions": [], "filters": {}, "analysis_type": "unsupported", "sql": None, "clarification_question": None}])
    unsupported = deps(FakeContext({"status": "unsupported"}), unsupported_provider, [])
    state = await build_workflow(unsupported).ainvoke(AskDataRequest(session_id="s", question="biaya iklan TV", provider="qwen", model="m").model_dump())
    assert state["status"] == "UNSUPPORTED"
    assert unsupported.query_executor.queries == []


@pytest.mark.asyncio
async def test_invalid_sql_gets_only_one_repair_attempt() -> None:
    provider = FakeProvider([
        {"strategy": "sql_fallback", "domains": ["sales"], "metrics": [], "dimensions": [], "filters": {}, "analysis_type": "metric", "sql": "DROP TABLE x", "clarification_question": None},
        {"strategy": "sql_fallback", "domains": ["sales"], "metrics": [], "dimensions": [], "filters": {}, "analysis_type": "metric", "sql": "SELECT d.value FROM gold.allowed d LIMIT 10", "clarification_question": None},
        analysis(),
    ])
    attempts = 0

    def validator(sql, context):
        nonlocal attempts
        attempts += 1
        return ValidatedSQL(attempts > 1, sql=sql if attempts > 1 else None, error=None if attempts > 1 else "DDL/DML statements are not allowed")

    state = await build_workflow(deps(FakeContext({"status": "unsupported"}), provider, [{"value": 1}], validator)).ainvoke(AskDataRequest(session_id="s", question="fallback", provider="openai", model="m").model_dump())

    assert state["status"] == "SUCCESS"
    assert state["retry_count"] == 1
    assert attempts == 2
    assert provider.calls == ["QueryPlan", "QueryPlan", "AnalysisOutput"]


@pytest.mark.asyncio
async def test_empty_result_is_no_data_and_invalid_chart_is_removed() -> None:
    no_data_provider = FakeProvider([])
    governed = FakeContext({"status": "resolved", "metric": "gross_billing_value", "definition": {"base_dataset": "monthly_executive"}})
    no_data = await build_workflow(deps(governed, no_data_provider, [])).ainvoke(AskDataRequest(session_id="s", question="gross", provider="qwen", model="m").model_dump())
    assert no_data["status"] == "NO_DATA"
    assert no_data_provider.calls == []

    invalid_chart_provider = FakeProvider([analysis({"type": "bar", "title": "Wrong", "x": "missing", "y": "value"})])
    invalid_chart = await build_workflow(deps(governed, invalid_chart_provider, [{"value": 1}])).ainvoke(AskDataRequest(session_id="s", question="gross", provider="qwen", model="m").model_dump())
    assert invalid_chart["chart_spec"] is None
