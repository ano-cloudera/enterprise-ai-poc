from __future__ import annotations

import sys
import types

import pytest

from app.db.base import DataBackendError
from app.db.impala_backend import ImpalaBackend


def test_impala_execute_returns_safe_error_and_telemetry(monkeypatch) -> None:
    backend = ImpalaBackend()

    def fail(_sql: str):
        raise RuntimeError("driver detail must not escape")

    monkeypatch.setattr(backend, "query", fail)
    with pytest.raises(DataBackendError) as error:
        backend.execute("SELECT 1")

    assert error.value.code == "IMPALA_QUERY_FAILED"
    assert error.value.telemetry is not None
    assert error.value.telemetry.success is False
    assert error.value.telemetry.safe_error_code == "IMPALA_QUERY_FAILED"
    assert "driver detail" not in str(error.value)


def _install_fake_impyla(monkeypatch, captured: dict) -> None:
    """impyla (the impala.dbapi module) isn't a hard backend dependency - it's
    only installed via requirements-impala.txt for real Impala deployments -
    so it may not be importable in a plain test environment. Fake it so
    ImpalaBackend.query()'s `from impala.dbapi import connect` resolves to a
    stand-in that just records what it was called with."""

    def fake_connect(**kwargs):
        captured.update(kwargs)

        class FakeCursor:
            description = [("n", None)]

            def execute(self, _sql):
                return None

            def fetchall(self):
                return [(1,)]

            def close(self):
                return None

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def close(self):
                return None

        return FakeConnection()

    dbapi_module = types.ModuleType("impala.dbapi")
    dbapi_module.connect = fake_connect
    impala_module = types.ModuleType("impala")
    impala_module.dbapi = dbapi_module
    monkeypatch.setitem(sys.modules, "impala", impala_module)
    monkeypatch.setitem(sys.modules, "impala.dbapi", dbapi_module)


def test_impala_query_omits_http_transport_by_default(monkeypatch) -> None:
    """Default settings (impala_use_http_transport=False, impala_http_path="")
    must reach the driver unchanged, so an existing direct-coordinator/binary
    Thrift setup keeps working exactly as before this option was added."""
    captured: dict = {}
    _install_fake_impyla(monkeypatch, captured)

    backend = ImpalaBackend()
    backend.query("SELECT 1")

    assert captured["use_http_transport"] is False
    assert captured["http_path"] == ""


def test_impala_query_passes_http_transport_when_configured(monkeypatch) -> None:
    """A gateway-fronted coordinator (e.g. a CDP Impala Virtual Warehouse
    reached over HTTPS) needs use_http_transport=True and an http_path -
    this is what makes that connection actually work instead of silently
    falling back to the binary protocol."""
    captured: dict = {}
    _install_fake_impyla(monkeypatch, captured)

    backend = ImpalaBackend()
    backend.settings.impala_use_http_transport = True
    backend.settings.impala_http_path = "cliservice"
    backend.query("SELECT 1")

    assert captured["use_http_transport"] is True
    assert captured["http_path"] == "cliservice"

