from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from app.core.config import Settings


logger = logging.getLogger(__name__)


def _klist_has_ticket() -> bool:
    try:
        proc = subprocess.run(["klist"], capture_output=True, text=True, check=False)
        body = proc.stdout + proc.stderr
        return proc.returncode == 0 and "Cache not found" not in body and "No credentials" not in body
    except FileNotFoundError:
        return False


def _should_kinit_on_start(settings: Settings) -> bool:
    if settings.impala_auth_mechanism.upper() != "GSSAPI":
        return False
    if settings.kerberos_kinit_on_start:
        return True
    return settings.impala_credential_profile.strip().lower() == "ingram"


def ensure_kerberos_ticket(settings: Settings) -> None:
    """Obtain a Kerberos TGT for GSSAPI Impala when using the Ingram profile (or explicit opt-in).

    Prefer ``KERBEROS_KEYTAB`` + ``KERBEROS_PRINCIPAL``. ``KERBEROS_PASSWORD`` is supported for
    non-interactive CAI only when operators accept storing a secret in Application env.
    """
    if not _should_kinit_on_start(settings):
        return

    principal = settings.kerberos_principal.strip()
    keytab = settings.kerberos_keytab.strip()
    password = settings.kerberos_password.get_secret_value().strip()

    if settings.krb5_config.strip():
        os.environ["KRB5_CONFIG"] = settings.krb5_config.strip()

    if not principal and not keytab:
        logger.info(
            "kerberos_kinit skipped profile=%s (set KERBEROS_PRINCIPAL and/or KERBEROS_KEYTAB)",
            settings.impala_credential_profile,
        )
        return

    if _klist_has_ticket() and not settings.kerberos_kinit_renew:
        logger.info("kerberos_kinit skipped (existing ticket in cache)")
        return

    env = os.environ.copy()
    try:
        if keytab:
            keytab_path = Path(keytab).expanduser()
            if not keytab_path.is_file():
                logger.warning("kerberos_kinit failed keytab_missing path=%s", keytab_path)
                return
            cmd = ["kinit", "-kt", str(keytab_path)]
            if principal:
                cmd.append(principal)
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        elif password and principal:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as handle:
                handle.write(password)
                handle.write("\n")
                pw_path = handle.name
            try:
                proc = subprocess.run(
                    ["kinit", "--password-file", pw_path, principal],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                )
            finally:
                Path(pw_path).unlink(missing_ok=True)
        else:
            logger.warning(
                "kerberos_kinit skipped principal=%r keytab_set=%s password_set=%s",
                principal or None,
                bool(keytab),
                bool(password),
            )
            return
    except FileNotFoundError:
        logger.warning("kerberos_kinit failed kinit_binary_not_found")
        return

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().replace("\n", " ")[:500]
        logger.warning(
            "kerberos_kinit failed exit=%s principal=%r detail=%s",
            proc.returncode,
            principal or None,
            detail or "unknown",
        )
        return

    logger.info("kerberos_kinit ok principal=%r", principal or "(keytab default)")
