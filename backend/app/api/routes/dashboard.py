from fastapi import APIRouter

from app.core.schemas import DashboardOverview, DashboardRequest
from app.services.dashboard import get_dashboard_overview

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/overview", response_model=DashboardOverview)
def overview() -> DashboardOverview:
    return DashboardOverview.model_validate(get_dashboard_overview())


@router.post("/dashboard/overview", response_model=DashboardOverview)
def overview_with_context(request: DashboardRequest) -> DashboardOverview:
    # request.context (filters/date-range) is accepted for API compatibility
    # with the frontend's existing POST payload, but the OSSIE dashboard is
    # a fixed Q4 2024 governed view and doesn't vary by it yet.
    del request
    return DashboardOverview.model_validate(get_dashboard_overview())
