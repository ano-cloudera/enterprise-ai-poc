from app.services import dashboard
from app.services.query import QueryResult


def test_dashboard_queries_pass_through_query_service(monkeypatch):
    purposes = []

    def execute(sql, context):
        purposes.append(context.purpose)
        if context.purpose.endswith("current_sales") or context.purpose.endswith("previous_sales"):
            rows = [{"sales": 100.0}]
        elif context.purpose.endswith("inventory_health"):
            rows = [{"healthy_pct": 90.0}]
        else:
            rows = []
        return QueryResult(sql=sql, columns=list(rows[0]) if rows else [], rows=rows)

    monkeypatch.setattr(dashboard.query_service, "execute_validated", execute)
    dashboard.get_dashboard_overview()
    assert len(purposes) == 7
    assert all(item.startswith("dashboard.") for item in purposes)
