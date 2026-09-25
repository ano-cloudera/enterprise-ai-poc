from __future__ import annotations

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
import logging

from app.api.routes import chat, config, dashboard, health, monitoring, semantic
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)
app = FastAPI(
    title="Enterprise AI PoC API",
    version="0.9.0",
    description="Reusable Cloudera AI PoC foundation with controlled LangGraph orchestration.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    health.router,
    config.router,
    dashboard.router,
    chat.router,
    monitoring.router,
    semantic.router,
):
    app.include_router(router, prefix=settings.api_prefix)


@app.exception_handler(Exception)
async def safe_unhandled_error(_: Request, error: Exception):
    trace_id = str(uuid.uuid4())
    logger.exception("Unhandled API error trace_id=%s", trace_id, exc_info=error)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error", "trace_id": trace_id},
    )


@app.get("/")
def root():
    return {
        "service": "enterprise-ai-poc",
        "version": "0.9.0",
        "project": settings.project_id,
        "docs": "/docs",
    }
