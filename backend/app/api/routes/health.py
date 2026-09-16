from datetime import datetime, timezone
from fastapi import APIRouter

from app.core.config import get_settings
from app.core.schemas import BackendHealth, HealthResponse
from app.db.factory import get_data_backend
from app.llm.factory import get_llm_provider

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    data_health = get_data_backend().health_check(probe=False)
    model = await get_llm_provider(settings).health_check()
    return HealthResponse(
        status="ok" if data_health.status != "degraded" else "degraded",
        app=settings.app_name,
        project=settings.project_id,
        data_backend=BackendHealth(
            status=data_health.status,
            name=data_health.type,
            type=data_health.type,
            catalog=data_health.catalog,
            schema=data_health.schema,
        ),
        model_backend=model.model_dump(),
        timestamp=datetime.now(timezone.utc),
    )
