from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.kerberos_bootstrap import ensure_kerberos_ticket


def _gssapi_ingram(**overrides: object) -> Settings:
    base = dict(
        impala_auth_mechanism="GSSAPI",
        impala_credential_profile="ingram",
        kerberos_principal="svc@IMID.LOCAL",
        kerberos_keytab="/secrets/svc.keytab",
        kerberos_password=SecretStr(""),
    )
    base.update(overrides)
    return Settings(**base)


def test_kinit_skipped_when_not_gssapi() -> None:
    settings = _gssapi_ingram(impala_auth_mechanism="LDAP")
    with patch("app.core.kerberos_bootstrap.subprocess.run") as run:
        ensure_kerberos_ticket(settings)
        run.assert_not_called()


def test_kinit_skipped_for_ingram_profile_without_opt_in() -> None:
    settings = _gssapi_ingram()
    with patch("app.core.kerberos_bootstrap.subprocess.run") as run:
        ensure_kerberos_ticket(settings)
        run.assert_not_called()


def test_kinit_keytab_when_no_ticket() -> None:
    settings = _gssapi_ingram(kerberos_kinit_on_start=True)
    with patch("app.core.kerberos_bootstrap._klist_has_ticket", return_value=False):
        with patch("app.core.kerberos_bootstrap.Path.is_file", return_value=True):
            with patch("app.core.kerberos_bootstrap.subprocess.run") as run:
                run.return_value.returncode = 0
                ensure_kerberos_ticket(settings)
                run.assert_called_once()
                assert run.call_args.args[0] == [
                    "kinit",
                    "-kt",
                    "/secrets/svc.keytab",
                    "svc@IMID.LOCAL",
                ]


def test_kinit_skipped_when_ticket_exists() -> None:
    settings = _gssapi_ingram()
    with patch("app.core.kerberos_bootstrap._klist_has_ticket", return_value=True):
        with patch("app.core.kerberos_bootstrap.subprocess.run") as run:
            ensure_kerberos_ticket(settings)
            run.assert_not_called()


def test_kinit_renew_when_flag_set() -> None:
    settings = _gssapi_ingram(kerberos_kinit_on_start=True, kerberos_kinit_renew=True)
    with patch("app.core.kerberos_bootstrap._klist_has_ticket", return_value=True):
        with patch("app.core.kerberos_bootstrap.Path.is_file", return_value=True):
            with patch("app.core.kerberos_bootstrap.subprocess.run") as run:
                run.return_value.returncode = 0
                ensure_kerberos_ticket(settings)
                run.assert_called_once()
