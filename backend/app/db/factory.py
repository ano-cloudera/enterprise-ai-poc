from functools import lru_cache

from app.core.config import get_settings
from app.db.duckdb_backend import DuckDBBackend
from app.db.impala_backend import ImpalaBackend
from app.db.trino_backend import TrinoBackend


def build_data_backend(settings):
    if settings.data_backend == "trino":
        return TrinoBackend(settings)
    if settings.data_backend == "impala":
        return ImpalaBackend()
    return DuckDBBackend(settings)


@lru_cache(maxsize=1)
def get_data_backend():
    settings = get_settings()
    return build_data_backend(settings)
