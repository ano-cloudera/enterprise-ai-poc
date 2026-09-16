import pytest

from app.core.schemas import ChatRequest
from app.services.chat import run_chat
from app.services.dashboard import get_dashboard_overview


@pytest.mark.asyncio
async def test_two_turn_context_dashboard_refresh_and_reset():
    first = await run_chat(ChatRequest(question="Kenapa sales Jawa Barat turun bulan ini?", session_id="shared-state-test"))
    assert first.status == "ok"
    assert first.metadata.resolved_context.filters["region"] == ["Jawa Barat"]
    assert first.metadata.resolved_context.date_range.preset == "current_month"

    second = await run_chat(ChatRequest(
        question="Kalau cuma Modern Trade?",
        session_id="shared-state-test",
        context=first.metadata.resolved_context,
    ))
    assert second.status == "ok"
    assert second.metadata.resolved_context.filters["region"] == ["Jawa Barat"]
    assert second.metadata.resolved_context.filters["channel"] == ["Modern Trade"]
    assert any(action.type == "SET_FILTER" and action.target == "channel" for action in second.ui_actions)

    baseline = get_dashboard_overview()
    filtered = get_dashboard_overview(second.metadata.resolved_context)
    baseline_sales = next(item["value"] for item in baseline["kpis"] if item["key"] == "net_sales")
    filtered_sales = next(item["value"] for item in filtered["kpis"] if item["key"] == "net_sales")
    assert filtered_sales < baseline_sales
    assert [row["region"] for row in filtered["region_sales"]] == ["Jawa Barat"]
    assert [row["channel"] for row in filtered["channel_share"]] == ["Modern Trade"]

    reset = await run_chat(ChatRequest(question="Reset filternya", session_id="shared-state-test", context=second.metadata.resolved_context))
    assert reset.metadata.resolved_context.filters == {}
    assert reset.metadata.resolved_context.dimension == "region"
    assert [action.type for action in reset.ui_actions] == ["RESET_FILTER"]
