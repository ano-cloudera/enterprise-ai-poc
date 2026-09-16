import pytest

from app.core.schemas import DashboardState
from app.graph.nodes import resolve_semantics
from app.services import dashboard
from app.services.query import QueryResult, QueryValidationError


def state(question: str, context: DashboardState):
    return resolve_semantics({"question": question, "dashboard_state": context.model_dump()})


def test_modern_trade_alias_preserves_prior_region_and_period():
    context = DashboardState(filters={"region": ["Jawa Barat"]}, date_range="current_month", metric="net_sales", dimension="region")
    resolved = state("Kalau cuma MT?", context)["resolved_state"]
    assert resolved["filters"]["region"] == ["Jawa Barat"]
    assert resolved["filters"]["channel"] == ["Modern Trade"]
    assert resolved["date_range"]["preset"] == "current_month"


def test_explicit_new_entity_overrides_prior_entity_from_project_alias():
    context = DashboardState(filters={"region": ["Jawa Barat"], "channel": ["Modern Trade"]}, date_range="current_month")
    resolved = state("Kalau East Java?", context)["resolved_state"]
    assert resolved["filters"]["region"] == ["Jawa Timur"]
    assert resolved["filters"]["channel"] == ["Modern Trade"]


def test_reset_request_is_resolved_as_a_reset_action():
    context = DashboardState(filters={"region": ["Jawa Barat"]}, date_range="current_month")
    resolved = state("Reset filternya", context)
    assert resolved["reset_requested"] is True
    assert resolved["resolved_state"]["filters"] == {}


def test_dashboard_overview_accepts_active_filters_and_changes_sql(monkeypatch):
    sql_seen = []

    def execute(sql, context):
        sql_seen.append(sql)
        purpose = context.purpose
        if purpose.endswith("current_sales") or purpose.endswith("previous_sales"):
            rows = [{"sales": 100.0}]
        elif purpose.endswith("inventory_health"):
            rows = [{"healthy_pct": 90.0}]
        else:
            rows = []
        return QueryResult(sql=sql, columns=list(rows[0]) if rows else [], rows=rows)

    monkeypatch.setattr(dashboard.query_service, "execute_validated", execute)
    context = DashboardState(filters={"region": ["Jawa Barat"], "channel": ["Modern Trade"]}, date_range="current_month")
    dashboard.get_dashboard_overview(context)
    joined = " ".join(sql_seen)
    assert "Jawa Barat" in joined
    assert "Modern Trade" in joined
    assert len(sql_seen) == 7


def test_invalid_dashboard_filter_value_is_rejected_safely():
    context = DashboardState(filters={"region": ["Not A Governed Region"]}, date_range="current_month")
    with pytest.raises(QueryValidationError):
        dashboard.get_dashboard_overview(context)
