from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.trino_backend import parse_trino_jdbc_url


class LoaderConfigurationError(RuntimeError):
    def __init__(self, code: str = "LOADER_CONFIGURATION_INCOMPLETE"):
        self.code = code
        super().__init__(code)


class LoaderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    trino_loader_jdbc_url: str = ""
    trino_loader_host: str = ""
    trino_loader_port: int = Field(default=443, ge=1, le=65535)
    trino_loader_http_scheme: Literal["http", "https"] = "https"
    trino_loader_catalog: str = ""
    trino_loader_schema: str = ""
    trino_loader_user: str = ""
    trino_loader_password: SecretStr = SecretStr("")
    trino_loader_access_token: SecretStr = SecretStr("")
    trino_loader_verify_ssl: bool = True
    trino_loader_connect_timeout_seconds: float = Field(default=10, gt=0, le=120)
    trino_loader_query_timeout_seconds: float = Field(default=120, gt=0, le=600)
    trino_loader_batch_size: int = Field(default=500, ge=1)
    trino_loader_dry_run: bool = False


@dataclass(frozen=True)
class LoaderConfig:
    host: str
    port: int
    http_scheme: str
    catalog: str
    schema: str
    user: str
    password: SecretStr
    access_token: SecretStr
    verify_ssl: bool
    connect_timeout_seconds: float
    query_timeout_seconds: float
    batch_size: int
    dry_run: bool

    @classmethod
    def from_settings(cls, settings: LoaderSettings) -> "LoaderConfig":
        if settings.trino_loader_jdbc_url:
            try:
                endpoint = parse_trino_jdbc_url(settings.trino_loader_jdbc_url)
                host, port, scheme = endpoint.host, endpoint.port, endpoint.http_scheme
            except ValueError:
                host, port, scheme = "", settings.trino_loader_port, settings.trino_loader_http_scheme
        else:
            host = settings.trino_loader_host.strip()
            port = settings.trino_loader_port
            scheme = settings.trino_loader_http_scheme
        return cls(
            host=host,
            port=port,
            http_scheme=scheme,
            catalog=settings.trino_loader_catalog.strip(),
            schema=settings.trino_loader_schema.strip(),
            user=settings.trino_loader_user.strip(),
            password=settings.trino_loader_password,
            access_token=settings.trino_loader_access_token,
            verify_ssl=settings.trino_loader_verify_ssl,
            connect_timeout_seconds=settings.trino_loader_connect_timeout_seconds,
            query_timeout_seconds=settings.trino_loader_query_timeout_seconds,
            batch_size=min(settings.trino_loader_batch_size, 500),
            dry_run=settings.trino_loader_dry_run,
        )

    @property
    def auth_kind(self) -> str:
        has_password = bool(self.password.get_secret_value())
        has_token = bool(self.access_token.get_secret_value())
        if has_password == has_token:
            raise LoaderConfigurationError()
        return "basic" if has_password else "token"

    def validate(self) -> None:
        if not all((self.host, self.catalog, self.schema)):
            raise LoaderConfigurationError()
        if self.dry_run:
            return
        if not self.user:
            raise LoaderConfigurationError()
        self.auth_kind

    def safe_summary(self) -> dict[str, object]:
        return {
            "endpoint": f"{self.host}:{self.port}" if self.host else "unconfigured",
            "tls": self.http_scheme == "https" and self.verify_ssl,
            "catalog": self.catalog or None,
            "schema": self.schema or None,
            "authentication": "configured" if bool(self.password.get_secret_value() or self.access_token.get_secret_value()) else "missing",
            "batch_size": self.batch_size,
            "dry_run": self.dry_run,
        }
