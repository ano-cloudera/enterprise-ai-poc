from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Enterprise AI PoC"
    app_env: str = "local"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    project_id: str = "tempo_scan"
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3] / "projects")

    data_backend: Literal["duckdb", "trino", "impala"] = "duckdb"
    duckdb_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3] / "runtime" / "tempo_scan.duckdb")

    trino_jdbc_url: str = ""
    trino_host: str = ""
    trino_port: int = Field(default=443, ge=1, le=65535)
    trino_http_scheme: Literal["http", "https"] = "https"
    trino_catalog: str = ""
    trino_schema: str = ""
    trino_user: str = ""
    trino_password: SecretStr = SecretStr("")
    trino_access_token: SecretStr = SecretStr("")
    trino_verify_ssl: bool = True
    trino_connect_timeout_seconds: float = Field(default=10, gt=0, le=120)
    trino_query_timeout_seconds: float = Field(default=60, gt=0, le=300)
    trino_max_rows: int = Field(default=500, ge=1, le=5000)

    impala_host: str = "localhost"
    impala_port: int = 21050
    impala_database: str = "default"
    impala_auth_mechanism: str = "PLAIN"
    impala_user: str = ""
    impala_password: str = ""
    impala_use_ssl: bool = False

    llm_mode: Literal["mock", "remote"] = "mock"
    qwen_base_url: str = ""
    qwen_model: str = "Qwen3.8-27B-AWQ"
    qwen_api_token: SecretStr = SecretStr("")
    qwen_request_timeout_seconds: float = Field(default=60, gt=0, le=300)
    qwen_max_retries: int = Field(default=1, ge=0, le=1)
    qwen_verify_ssl: bool = True
    qwen_disable_thinking: bool = True
    qwen_max_tokens: int = Field(default=1400, ge=100, le=8000)

    # When set, the backend routes LLM calls through this LiteLLM proxy
    # (litellm/config.yaml's "commercial-intelligence" model group) instead
    # of calling Qwen directly. Empty by default so existing deployments
    # that haven't stood up the LiteLLM Application keep working unchanged.
    litellm_base_url: str = ""
    litellm_api_key: SecretStr = SecretStr("")
    litellm_model_group: str = "commercial-intelligence"
    # The Agent Studio workflow group name in litellm/config.yaml. Not
    # callable yet (see litellm/config.yaml) — kept here so the routing
    # decision of "should we prefer Agent Studio" lives in one place once
    # it is provisioned, rather than being hardcoded at call sites.
    litellm_agent_studio_model_group: str = "agent-studio-workflow"
    litellm_use_agent_studio: bool = False

    serpapi_api_key: SecretStr = SecretStr("")
    serpapi_enabled: bool = True
    serpapi_max_queries: int = Field(default=5, ge=1, le=11)
    serper_api_key: SecretStr = SecretStr("")
    serper_enabled: bool = True
    serper_max_queries: int = Field(default=5, ge=1, le=11)
    market_api_base_url: str = "http://127.0.0.1:8100"

    @property
    def market_collector_api_key(self) -> str:
        """Prefer the correct Serper key; retain the old variable during migration."""
        return self.serper_api_key.get_secret_value() or self.serpapi_api_key.get_secret_value()

    sql_max_rows: int = 500
    sql_max_repair_attempts: int = 1

    guardrails_enabled: bool = False
    guardrails_api_key: str = ""
    guardrails_token: str = ""

    telemetry_db_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3] / "runtime" / "telemetry.sqlite")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def project_dir(self) -> Path:
        return self.project_root / self.project_id


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
