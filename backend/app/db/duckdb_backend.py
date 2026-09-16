from __future__ import annotations

from pathlib import Path
from threading import Lock
from time import monotonic
import duckdb

from app.core.config import get_settings
from app.db.base import BackendColumn, BackendExecutionContext, BackendQueryResult, DataBackendHealth, QueryTelemetry, normalize_value


class DuckDBBackend:
    dialect = "duckdb"

    def __init__(self, settings=None) -> None:
        self.settings = settings or get_settings()
        self.db_path = Path(self.settings.duckdb_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
        self._initialize_lock = Lock()

    def connect(self):
        return duckdb.connect(str(self.db_path))

    def health(self) -> tuple[str, str]:
        fixtures = self.settings.project_dir / "fixtures"
        ready = (fixtures / "commercial_sales_daily.csv").exists() and (fixtures / "commercial_inventory_daily.csv").exists()
        return ("ok" if ready else "degraded", "duckdb")

    def health_check(self, probe: bool = False) -> DataBackendHealth:
        status, _ = self.health()
        return DataBackendHealth(type="duckdb", status=status)

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._initialize_lock:
            if self._initialized:
                return
            fixtures = self.settings.project_dir / "fixtures"
            sales = fixtures / "commercial_sales_daily.csv"
            inventory = fixtures / "commercial_inventory_daily.csv"
            product_master = fixtures / "commercial_product_master.csv"
            if not sales.exists() or not inventory.exists():
                raise FileNotFoundError("Sample fixtures missing. Run scripts/generate_sample_data.py")
            with self.connect() as con:
                con.execute("DROP TABLE IF EXISTS commercial_sales_daily")
                con.execute("DROP TABLE IF EXISTS commercial_inventory_daily")
                sales_path = str(sales).replace("'", "''")
                inventory_path = str(inventory).replace("'", "''")
                con.execute(f"CREATE TABLE commercial_sales_daily AS SELECT * FROM read_csv_auto('{sales_path}')")
                con.execute(f"CREATE TABLE commercial_inventory_daily AS SELECT * FROM read_csv_auto('{inventory_path}')")
                if product_master.exists():
                    product_path = str(product_master).replace("'", "''")
                    con.execute("DROP TABLE IF EXISTS commercial_product_master")
                    con.execute(f"CREATE TABLE commercial_product_master AS SELECT * FROM read_csv_auto('{product_path}')")
            self._initialized = True

    def execute(self, sql: str, context: BackendExecutionContext | None = None) -> BackendQueryResult:
        self.initialize()
        started = monotonic()
        with self.connect() as con:
            cursor = con.execute(sql)
            description = cursor.description or []
            rows = cursor.fetchall()
        normalized = [[normalize_value(value) for value in row] for row in rows]
        columns = [BackendColumn(name=str(item[0]), type=str(item[1]).lower()) for item in description]
        telemetry = QueryTelemetry(
            data_backend="duckdb",
            query_latency_ms=(monotonic() - started) * 1000,
            row_count=len(normalized),
            success=True,
        )
        return BackendQueryResult(columns=columns, rows=normalized, row_count=len(normalized), telemetry=telemetry)

    def query(self, sql: str) -> list[dict]:
        return self.execute(sql).records()

    def close(self) -> None:
        return None
