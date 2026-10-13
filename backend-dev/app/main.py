from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, models, random_queries, usage
from app.api.v1 import projects as v1_projects
from app.api.v1 import workspaces as v1_workspaces
from app.stores.factory import build_conversation_store, build_usage_store, init_postgres_platform, log_active_stores
from app.core.config import Settings, get_settings
from app.llm.registry import ProviderRegistry
from app.services.chat import ChatService
from app.services.puppygraph_client import PuppyGraphClient
from app.db.duckdb_governed_backend import is_duckdb_governed_configured
from app.db.impala_backend import is_impala_configured


logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(application: FastAPI):
    settings: Settings = application.state.settings
    try:
        init_postgres_platform(settings)
    except Exception:
        logger.exception("platform bootstrap failed")
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()
    application = FastAPI(title=configured.app_name, version="2.0.0", lifespan=_lifespan)
    application.state.settings = configured
    application.state.provider_registry = ProviderRegistry(configured)
    usage_store = build_usage_store(configured)
    conversation_store = build_conversation_store(configured)
    log_active_stores(configured, conversation_store, usage_store)
    application.state.usage_store = usage_store
    application.state.chat_service = ChatService(
        configured,
        history=conversation_store,
        usage_store=usage_store,
    )
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
        use_duckdb = configured.data_backend.strip().lower() == "duckdb"
        impala_ready = is_duckdb_governed_configured(configured) if use_duckdb else is_impala_configured(configured)
        gemini = next(
            (m for m in application.state.provider_registry.list_models() if m.provider == "gemini"),
            None,
        )
        state_store = configured.state_store.strip().lower()
        postgres_configured = bool((configured.database_url or "").strip())
        components = {
            "state_store": state_store,
            "postgres_configured": postgres_configured,
            "llm": "ready" if llm_ready else "not_configured",
            "gemini_model": configured.gemini_model,
            "gemini_available": bool(gemini and gemini.available),
            "default_llm_provider": configured.default_llm_provider,
            "impala": "ready" if impala_ready else "not_configured",
            "data_backend": configured.data_backend.strip().lower(),
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
    application.include_router(v1_workspaces.router, prefix="/api/v1")
    application.include_router(v1_projects.router, prefix="/api/v1")
    return application


app = create_app()
