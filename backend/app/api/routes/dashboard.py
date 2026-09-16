from fastapi import APIRouter

from app.core.schemas import DashboardOverview, DashboardRequest
from app.services.dashboard import get_dashboard_overview

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/overview", response_model=DashboardOverview)
def overview() -> DashboardOverview:
    return DashboardOverview.model_validate(get_dashboard_overview())


@router.post("/dashboard/overview", response_model=DashboardOverview)
def overview_with_context(request: DashboardRequest) -> DashboardOverview:
    return DashboardOverview.model_validate(get_dashboard_overview(request.context))
