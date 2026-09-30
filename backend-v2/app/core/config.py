from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


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
    default_llm_provider: str = "qwen"

    qwen_base_url: str = ""
    qwen_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("QWEN_API_KEY", "QWEN_API_TOKEN"),
    )
    qwen_model: str = ""
    qwen_verify_ssl: bool = True

    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""

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
    conversation_db_path: Path = BACKEND_ROOT / "runtime" / "conversation_history.sqlite"

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
