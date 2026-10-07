from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import duckdb

from app.sql.guard import validate_readonly_sql


class DuckDBCatalog:
    def __init__(self, db_path: Path, *, sql_max_rows: int = 200) -> None:
        self.db_path = Path(db_path)
        self.sql_max_rows = sql_max_rows
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path), read_only=False)

    def list_tables(self) -> list[dict[str, str]]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT table_schema AS schema, table_name AS name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_schema, table_name
                """
            ).fetchall()
        return [{"schema": schema, "name": name, "qualified": f"{schema}.{name}"} for schema, name in rows]

    def describe_table(self, qualified_name: str) -> dict[str, Any]:
        parts = qualified_name.replace('"', "").split(".")
        if len(parts) != 2:
            raise ValueError("Use schema.table (e.g. silver.sales_oct_dec_2024)")
        schema, name = parts
        if schema != "silver":
            raise ValueError("Only silver.* tables are exposed to the agent")
        with self._connect() as con:
            cols = con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = ? AND table_name = ?
                ORDER BY ordinal_position
                """,
                [schema, name],
            ).fetchall()
            count = con.execute(f'SELECT COUNT(*) FROM "{schema}"."{name}"').fetchone()[0]
        return {
            "table": f"{schema}.{name}",
            "row_count": int(count),
            "columns": [{"name": c, "type": t} for c, t in cols],
        }

    def run_sql(self, sql: str) -> dict[str, Any]:
        checked = validate_readonly_sql(sql, max_rows=self.sql_max_rows)
        if not checked.ok:
            raise ValueError(checked.error or "Invalid SQL")
        started = time.perf_counter()
        with self._connect() as con:
            cursor = con.execute(checked.sql or "")
            description = cursor.description or []
            columns = [col[0] for col in description]
            raw_rows = cursor.fetchall()
        rows: list[dict[str, Any]] = []
        for raw in raw_rows:
            item: dict[str, Any] = {}
            for idx, col in enumerate(columns):
                value = raw[idx]
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                item[col] = value
            rows.append(item)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_ms": elapsed_ms,
            "sql": checked.sql,
        }

    def stats(self) -> dict[str, Any]:
        tables = self.list_tables()
        return {
            "duckdb_path": str(self.db_path),
            "table_count": len(tables),
            "tables": [t["qualified"] for t in tables],
        }


def observation_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)
