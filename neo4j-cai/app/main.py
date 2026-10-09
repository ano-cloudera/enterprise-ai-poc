"""Tempo Scan Neo4j Ontology — CAI sidecar (health, seed, read-only catalog)."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class OntologySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env", "../backend/.env"), extra="ignore")

    neo4j_uri: str = Field(default="", validation_alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    neo4j_password: SecretStr = Field(default=SecretStr(""), validation_alias="NEO4J_PASSWORD")
    neo4j_auto_seed: bool = Field(default=False, validation_alias="NEO4J_AUTO_SEED")
    neo4j_seed_clear: bool = Field(default=False, validation_alias="NEO4J_SEED_CLEAR")
    backend_root: str = Field(default="", validation_alias="TEMPO_BACKEND_ROOT")


def _settings() -> OntologySettings:
    return OntologySettings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = _settings()
    app.state.settings = settings
    pwd = settings.neo4j_password.get_secret_value()
    if settings.neo4j_auto_seed and settings.neo4j_uri and pwd:
        try:
            from neo4j import GraphDatabase

            from app.knowledge.neo4j_seed import seed_domain_graph

            driver = GraphDatabase.driver(
                settings.neo4j_uri.strip(),
                auth=(settings.neo4j_user.strip(), pwd),
            )
            with driver.session() as session:
                counts = seed_domain_graph(session, clear=settings.neo4j_seed_clear)
            driver.close()
            logger.info("neo4j_auto_seed_ok counts=%s", counts)
        except Exception:
            logger.exception("neo4j_auto_seed_failed")
    yield


app = FastAPI(title="TEMPO Neo4j Ontology", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness() -> dict[str, Any]:
    settings = _settings()
    pwd = settings.neo4j_password.get_secret_value()
    if not settings.neo4j_uri or not pwd:
        return {
            "status": "not_ready",
            "reason": "NEO4J_URI and NEO4J_PASSWORD required",
        }
    from app.core.config import Settings
    from app.services.neo4j_client import Neo4jKnowledgeClient

    client_settings = Settings(
        neo4j_enabled=True,
        neo4j_uri=settings.neo4j_uri,
        neo4j_user=settings.neo4j_user,
        neo4j_password=settings.neo4j_password,
    )
    client = Neo4jKnowledgeClient(client_settings)
    summary = client.schema_summary()
    ready = bool(summary.get("connected"))
    return {"status": "ready" if ready else "not_ready", "neo4j": summary}


@app.post("/admin/seed")
def admin_seed(clear: bool = False) -> dict[str, Any]:
    settings = _settings()
    pwd = settings.neo4j_password.get_secret_value()
    if not settings.neo4j_uri or not pwd:
        return {"status": "error", "message": "Neo4j not configured"}
    from neo4j import GraphDatabase

    from app.knowledge.neo4j_seed import seed_domain_graph

    driver = GraphDatabase.driver(
        settings.neo4j_uri.strip(),
        auth=(settings.neo4j_user.strip(), pwd),
    )
    try:
        with driver.session() as session:
            counts = seed_domain_graph(session, clear=clear or settings.neo4j_seed_clear)
        return {"status": "ok", "counts": counts}
    finally:
        driver.close()


@app.get("/ontology/governed-intents")
def list_governed_intents() -> dict[str, Any]:
    from app.core.config import Settings
    from app.services.neo4j_client import Neo4jKnowledgeClient

    settings = _settings()
    client = Neo4jKnowledgeClient(
        Settings(
            neo4j_enabled=True,
            neo4j_uri=settings.neo4j_uri,
            neo4j_user=settings.neo4j_user,
            neo4j_password=settings.neo4j_password,
        )
    )
    return {"intents": client.list_governed_intents()}
