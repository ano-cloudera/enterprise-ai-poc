from __future__ import annotations

from app.core.config import get_settings
from app.db.base import BackendColumn, BackendExecutionContext, BackendQueryResult, DataBackendHealth, QueryTelemetry, normalize_value


class ImpalaBackend:
    dialect = "hive"
    def __init__(self) -> None:
        self.settings = get_settings()

    def health(self) -> tuple[str, str]:
        configured = bool(self.settings.impala_host and self.settings.impala_user)
        return ("configured" if configured else "degraded", "impala")

    def health_check(self, probe: bool = False) -> DataBackendHealth:
        configured = bool(self.settings.impala_host and self.settings.impala_user)
        return DataBackendHealth(type="impala", status="unknown" if configured else "misconfigured")

    def query(self, sql: str) -> list[dict]:
        try:
            from impala.dbapi import connect
        except ImportError as exc:
            raise RuntimeError("Impala dependencies are not installed. Use requirements-impala.txt") from exc

        conn = connect(
            host=self.settings.impala_host,
            port=self.settings.impala_port,
            database=self.settings.impala_database,
            auth_mechanism=self.settings.impala_auth_mechanism,
            user=self.settings.impala_user or None,
            password=self.settings.impala_password or None,
            use_ssl=self.settings.impala_use_ssl,
        )
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    def execute(self, sql: str, context: BackendExecutionContext | None = None) -> BackendQueryResult:
        records = self.query(sql)
        names = list(records[0]) if records else []
        rows = [[normalize_value(record.get(name)) for name in names] for record in records]
        return BackendQueryResult(
            columns=[BackendColumn(name=name, type="unknown") for name in names],
            rows=rows,
            row_count=len(rows),
            telemetry=QueryTelemetry(
                data_backend="impala",
                query_latency_ms=0,
                row_count=len(rows),
                success=True,
            ),
        )

    def close(self) -> None:
        return None
