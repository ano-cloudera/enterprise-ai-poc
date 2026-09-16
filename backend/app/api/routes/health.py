from datetime import datetime, timezone
from fastapi import APIRouter
import httpx

from app.core.config import get_settings
from app.core.schemas import BackendHealth, ComponentReadiness, HealthResponse, ReadinessResponse
from app.db.factory import get_data_backend
from app.llm.factory import get_llm_provider
from app.semantic.loader import load_semantic_project

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


@router.get("/deployment/readiness", response_model=ReadinessResponse)
async def deployment_readiness() -> ReadinessResponse:
    """Aggregate deployment health for the CAI application: backend API,
    semantic layer, data backend, Mock Market API, and Qwen configuration.
    Never exposes secrets, tokens, or raw error payloads."""
    settings = get_settings()
    components: list[ComponentReadiness] = [
        ComponentReadiness(name="backend_api", status="healthy", detail="FastAPI process reachable"),
    ]

    try:
        project = load_semantic_project(settings.project_id)
        components.append(ComponentReadiness(name="semantic_layer", status="healthy", detail=f"{len(project.datasets)} dataset(s) loaded"))
    except Exception:
        components.append(ComponentReadiness(name="semantic_layer", status="unavailable", detail="Semantic project failed to load"))

    data_health = get_data_backend().health_check(probe=False)
    components.append(ComponentReadiness(
        name="data_backend",
        status="healthy" if data_health.status in ("ok",) else "degraded" if data_health.status == "degraded" else "unavailable",
        detail=f"{data_health.type} backend",
    ))

    market_status, market_detail = "unavailable", "Mock Market API not reachable"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.market_api_base_url}/health")
            if response.status_code == 200:
                market_status, market_detail = "healthy", "Mock Market API reachable"
            else:
                market_status, market_detail = "degraded", "Mock Market API returned a non-200 response"
    except Exception:
        pass
    components.append(ComponentReadiness(name="market_api", status=market_status, detail=market_detail))

    model = await get_llm_provider(settings).health_check()
    if model.mode == "mock":
        components.append(ComponentReadiness(name="llm_provider", status="healthy", detail="Mock LLM provider configured"))
    elif model.status == "ok":
        components.append(ComponentReadiness(name="llm_provider", status="healthy", detail="Qwen endpoint configured"))
    elif model.status == "unknown":
        components.append(ComponentReadiness(name="llm_provider", status="degraded", detail="Qwen endpoint configured, connectivity not probed"))
    else:
        components.append(ComponentReadiness(name="llm_provider", status="unavailable", detail="Qwen endpoint not configured"))

    statuses = {component.status for component in components}
    overall = "unavailable" if "unavailable" in statuses else "degraded" if "degraded" in statuses else "healthy"

    return ReadinessResponse(
        status=overall,
        app=settings.app_name,
        project=settings.project_id,
        components=components,
        timestamp=datetime.now(timezone.utc),
    )
