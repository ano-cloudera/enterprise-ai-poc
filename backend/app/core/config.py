from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.core.impala_env import load_impala_profile
from app.core.llm_env import gemini_model_from_env_files


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", BACKEND_ROOT.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "TEMPO Scan Commercial Intelligence V2"
    app_env: str = "local"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    default_llm_provider: str = "gemini"

    qwen_base_url: str = ""
    qwen_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("QWEN_API_KEY", "QWEN_API_TOKEN"),
    )
    qwen_model: str = ""
    qwen_verify_ssl: bool = True

    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    gemini_model: str = Field(
        default="gemini-3.8-flash",
        validation_alias=AliasChoices("GEMINI_MODEL", "MODEL_GEMINI"),
    )

    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    openai_verify_ssl: bool = True

    llm_request_timeout_seconds: float = Field(default=60, gt=0, le=300)
    llm_max_tokens: int = Field(default=1800, ge=100, le=8000)

    project_root: Path = BACKEND_ROOT / "projects"
    ossie_project_id: str = "tempo_scan_impala"
    sql_max_rows: int = Field(default=200, ge=1, le=1000)
    impala_host: str = "localhost"
    impala_port: int = 21050
    impala_database: str = "gold"
    impala_auth_mechanism: str = "PLAIN"
    impala_user: str = ""
    impala_password: str = ""
    impala_use_ssl: bool = False
    impala_use_http_transport: bool = False
    impala_http_path: str = ""
    impala_kerberos_service_name: str = "impala"
    impala_query_timeout_seconds: int = Field(default=60, ge=1, le=600)
    # When set to `aws` or `ingram`, load IMPALA_* from that labeled block in repo `.env`
    # (see ### IMPALA CREDENTIALS … ENV sections). Avoids duplicate-key override bugs.
    impala_credential_profile: str = "aws"
    conversation_db_path: Path = BACKEND_ROOT / "runtime" / "conversation_history.sqlite"
    usage_db_path: Path = Field(
        default=BACKEND_ROOT / "runtime" / "llm_usage.sqlite",
        validation_alias="USAGE_DB_PATH",
    )
    usage_monthly_token_budget: int = Field(
        default=0,
        ge=0,
        validation_alias="USAGE_MONTHLY_TOKEN_BUDGET",
        description="Optional soft cap for Usage UI (0 = hidden)",
    )

    # Optional fallback: a separately governed sibling system (TEMPO Local
    # Agent) queried only when our own OSSIE-driven planner can't match a
    # published metric at all (strategy=unsupported). Disabled by default -
    # empty base_url means the fallback node is skipped entirely, so
    # existing behavior is unchanged unless an operator opts in.
    local_agent_base_url: str = ""
    # When true and base_url is set, force tempo_agent_v3 (legacy; prefer ask_data_routing=v3).
    local_agent_primary: bool = False
    # auto | ossie | v3 — see app/services/ask_data_routing.py
    ask_data_routing: str = "auto"
    local_agent_timeout_seconds: float = Field(default=180, gt=0, le=600)
    local_agent_engine: str = "langgraph"
    local_agent_max_attempts: int = Field(default=2, ge=1, le=5)
    local_agent_retry_delay_seconds: float = Field(default=2.0, ge=0, le=30)

    # OSSIE workflow answer-quality loop (Phase B1)
    judge_max_iterations: int = Field(default=2, ge=0, le=5)
    judge_enabled: bool = True

    # In-process TEMPO domain graph (knowledge/tempo_domain_graph.yaml)
    business_graph_enabled: bool = Field(default=True, validation_alias="BUSINESS_GRAPH_ENABLED")

    # Phase C7 — optional PuppyGraph (off critical path; schema stub in knowledge/)
    puppygraph_enabled: bool = Field(default=False, validation_alias="PUPPYGRAPH_ENABLED")
    puppygraph_base_url: str = Field(default="", validation_alias="PUPPYGRAPH_BASE_URL")

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    updates: dict = {}
    profile = settings.impala_credential_profile.strip().lower()
    if profile:
        updates.update(load_impala_profile(REPO_ROOT / ".env", profile) or {})
    gemini_from_env = gemini_model_from_env_files(backend_root=BACKEND_ROOT, repo_root=REPO_ROOT)
    if gemini_from_env:
        updates["gemini_model"] = gemini_from_env
    elif not (settings.gemini_model or "").strip() and settings.gemini_api_key.get_secret_value():
        updates["gemini_model"] = "gemini-3.8-flash"
    if updates:
        return settings.model_copy(update=updates)
    return settings
