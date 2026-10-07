from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, models, random_queries
from app.core.config import Settings, get_settings
from app.db.duckdb_catalog import DuckDBCatalog
from app.llm.registry import ProviderRegistry
from app.services.exploratory_agent import ExploratoryAgentService


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()
    application = FastAPI(title=configured.app_name, version="3.0.0")
    application.state.settings = configured
    application.state.provider_registry = ProviderRegistry(configured)
    application.state.catalog = DuckDBCatalog(
        configured.duckdb_path,
        sql_max_rows=configured.sql_max_rows,
    )
    application.state.chat_service = ExploratoryAgentService(
        configured,
        catalog=application.state.catalog,
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
        return {"status": "ok", "mode": "exploratory_local"}

    @application.get("/health/ready")
    def readiness() -> JSONResponse:
        llm_ready = any(model.available for model in application.state.provider_registry.list_models())
        duckdb_ready = configured.duckdb_path.exists()
        components = {
            "llm": "ready" if llm_ready else "not_configured",
            "duckdb": "ready" if duckdb_ready else "missing",
            "mode": "exploratory_local",
        }
        if duckdb_ready:
            components["catalog"] = application.state.catalog.stats()
        ready = llm_ready and duckdb_ready
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not_ready", "components": components},
        )

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
    return application


app = create_app()
