from __future__ import annotations

from pathlib import Path
import re

import duckdb

from app.forecasting.models import ForecastRow


FORECAST_TABLE = "commercial_sales_forecast"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FORECAST_COLUMNS = (
    "forecast_date", "generated_at", "forecast_horizon", "forecast_sales", "lower_bound", "upper_bound",
    "model_name", "model_version", "training_cutoff_date", "dimension_type", "dimension_value",
)


class ForecastWriteSafetyError(RuntimeError):
    pass


class LocalForecastWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, rows: list[ForecastRow]) -> None:
        with duckdb.connect(str(self.path)) as connection:
            connection.execute(
                f"""CREATE TABLE IF NOT EXISTS {FORECAST_TABLE} (
                    forecast_date DATE, generated_at TIMESTAMP, forecast_horizon BIGINT,
                    forecast_sales DOUBLE, lower_bound DOUBLE, upper_bound DOUBLE,
                    model_name VARCHAR, model_version VARCHAR, training_cutoff_date DATE,
                    dimension_type VARCHAR, dimension_value VARCHAR
                )"""
            )
            if not rows:
                return
            connection.execute(f"DELETE FROM {FORECAST_TABLE} WHERE model_version = ?", [rows[0].model_version])
            connection.executemany(
                f"INSERT INTO {FORECAST_TABLE} ({', '.join(FORECAST_COLUMNS)}) VALUES ({', '.join('?' for _ in FORECAST_COLUMNS)})",
                [[getattr(row, column) for column in FORECAST_COLUMNS] for row in rows],
            )

    def count(self) -> int:
        with duckdb.connect(str(self.path)) as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {FORECAST_TABLE}").fetchone()[0]


class TrinoForecastWriter:
    """Offline writer helper. Connection/identity is supplied only by an operator job."""

    @staticmethod
    def validate_target(catalog: str, schema: str, table: str = FORECAST_TABLE) -> str:
        if table != FORECAST_TABLE or not all(_IDENTIFIER.fullmatch(value) for value in (catalog, schema, table)):
            raise ForecastWriteSafetyError("FORECAST_TARGET_REJECTED")
        return f"{catalog}.{schema}.{table}"

    @classmethod
    def write(cls, cursor, rows: list[ForecastRow], catalog: str, schema: str) -> None:
        target = cls.validate_target(catalog, schema)
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {target} (forecast_date DATE, generated_at VARCHAR, forecast_horizon BIGINT, "
            "forecast_sales DOUBLE, lower_bound DOUBLE, upper_bound DOUBLE, model_name VARCHAR, model_version VARCHAR, "
            "training_cutoff_date DATE, dimension_type VARCHAR, dimension_value VARCHAR)"
        )
        if not rows:
            return
        version = rows[0].model_version.replace("'", "''")
        cursor.execute(f"DELETE FROM {target} WHERE model_version = '{version}'")
        placeholders = "(" + ", ".join("?" for _ in FORECAST_COLUMNS) + ")"
        for offset in range(0, len(rows), 500):
            batch = rows[offset : offset + 500]
            sql = f"INSERT INTO {target} ({', '.join(FORECAST_COLUMNS)}) VALUES " + ", ".join(placeholders for _ in batch)
            parameters = [getattr(row, column).isoformat() if hasattr(getattr(row, column), "isoformat") else getattr(row, column) for row in batch for column in FORECAST_COLUMNS]
            cursor.execute(sql, parameters)
