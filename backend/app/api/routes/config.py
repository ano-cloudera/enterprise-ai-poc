from fastapi import APIRouter

from app.core.config import get_settings
from app.core.runtime_settings import runtime_settings
from app.core.schemas import PublicConfigResponse, SettingsPatch
from app.guardrails.service import GuardrailService
from app.services.project import load_project_config

router = APIRouter(tags=["config"])


@router.get("/config/public", response_model=PublicConfigResponse)
def public_config() -> PublicConfigResponse:
    settings = get_settings()
    project = load_project_config()
    runtime = runtime_settings.get()
    return PublicConfigResponse(
        project_id=settings.project_id,
        project_name=project.get("name", settings.project_id),
        project_subtitle=project.get("subtitle", "Enterprise AI PoC"),
        brand=project.get("brand", {}),
        model_name=runtime["model_name"],
        data_backend=settings.data_backend,
        guardrails_enabled=settings.guardrails_enabled,
    )


@router.get("/settings")
def get_runtime_settings():
    settings = get_settings()
    runtime = runtime_settings.get()
    return {
        **runtime,
        "data_backend": settings.data_backend,
        "llm_mode": settings.llm_mode,
        "guardrails": GuardrailService().status,
    }


@router.put("/settings")
def update_runtime_settings(patch: SettingsPatch):
    runtime_settings.update(patch.model_dump(exclude_none=True))
    return get_runtime_settings()
