from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", BACKEND_ROOT.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "TEMPO Scan Exploratory Local (V3)"
    app_env: str = "local"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    default_llm_provider: str = "gemini"

    duckdb_path: Path = BACKEND_ROOT / "runtime" / "tempo_local.duckdb"
    agent_max_steps: int = Field(default=8, ge=1, le=20)
    sql_max_rows: int = Field(default=200, ge=1, le=1000)
    sql_query_timeout_seconds: float = Field(default=30, gt=0, le=120)

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
    openai_model: str = "gpt-4o-mini"
    openai_verify_ssl: bool = True

    llm_request_timeout_seconds: float = Field(default=90, gt=0, le=300)
    llm_max_tokens: int = Field(default=2200, ge=100, le=8000)

    knowledge_dir: Path = BACKEND_ROOT / "knowledge"
    parquet_sample_dir: Path = BACKEND_ROOT / "local_data" / "parquet"

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    from app.core.llm_env import gemini_model_from_env_files

    settings = Settings()
    updates: dict = {}
    gemini_from_env = gemini_model_from_env_files(backend_root=BACKEND_ROOT, repo_root=REPO_ROOT)
    if gemini_from_env:
        updates["gemini_model"] = gemini_from_env
    elif not (settings.gemini_model or "").strip() and settings.gemini_api_key.get_secret_value():
        updates["gemini_model"] = "gemini-3.8-flash"
    if updates:
        return settings.model_copy(update=updates)
    return settings
