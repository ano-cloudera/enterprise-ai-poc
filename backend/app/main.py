from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, models, random_queries, usage
from app.services.usage_store import UsageStore
from app.core.config import Settings, get_settings
from app.llm.registry import ProviderRegistry
from app.services.chat import ChatService
from app.services.puppygraph_client import PuppyGraphClient
from app.core.kerberos_bootstrap import ensure_kerberos_ticket
from app.db.impala_backend import is_impala_configured


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()
    ensure_kerberos_ticket(configured)
    application = FastAPI(title=configured.app_name, version="2.0.0")
    application.state.settings = configured
    application.state.provider_registry = ProviderRegistry(configured)
    application.state.chat_service = ChatService(configured)
    application.state.usage_store = UsageStore(configured.usage_db_path)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready")
    def readiness() -> JSONResponse:
        llm_ready = any(model.available for model in application.state.provider_registry.list_models())
        impala_ready = is_impala_configured(configured)
        gemini = next(
            (m for m in application.state.provider_registry.list_models() if m.provider == "gemini"),
            None,
        )
        components = {
            "llm": "ready" if llm_ready else "not_configured",
            "gemini_model": configured.gemini_model,
            "gemini_available": bool(gemini and gemini.available),
            "default_llm_provider": configured.default_llm_provider,
            "impala": "ready" if impala_ready else "not_configured",
            "semantic": "ready",
            "ask_data_routing": configured.ask_data_routing,
            "local_agent_base_url": configured.local_agent_base_url or None,
            "business_graph": "enabled" if configured.business_graph_enabled else "disabled",
            "puppygraph": PuppyGraphClient(configured).schema_summary(),
        }
        ready = llm_ready and impala_ready
        return JSONResponse(status_code=200 if ready else 503, content={"status": "ready" if ready else "not_ready", "components": components})

    @application.exception_handler(Exception)
    async def safe_error(_: Request, error: Exception):
        request_id = str(uuid.uuid4())
        logger.exception("unhandled_error request_id=%s", request_id, exc_info=error)
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": "Internal server error", "request_id": request_id},
        )

    application.include_router(models.router)
    application.include_router(random_queries.router)
    application.include_router(chat.router)
    application.include_router(usage.router)
    return application


app = create_app()
