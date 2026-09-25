from functools import lru_cache

from app.core.config import get_settings


def build_data_backend(settings):
    if settings.data_backend == "trino":
        from app.db.trino_backend import TrinoBackend

        return TrinoBackend(settings)
    if settings.data_backend == "impala":
        from app.db.impala_backend import ImpalaBackend

        return ImpalaBackend()
    from app.db.duckdb_backend import DuckDBBackend

    return DuckDBBackend(settings)


@lru_cache(maxsize=1)
def get_data_backend():
    settings = get_settings()
    return build_data_backend(settings)
