"""Cloudera AI Application entrypoint for the "Tempo Scan LiteLLM Router"
application.

Follows the CAI Application execution model used by backend/app_cai_backend.py
and frontend/app_cai_frontend.py: no reliance on __file__, no assumption that
CDSW_PROJECT_DIR is set or correct, binds 127.0.0.1 only (CAI's own reverse
proxy handles external exposure).

Runs the LiteLLM proxy (litellm/config.yaml) as this Application's listener.
The FastAPI backend calls this Application's URL (LITELLM_BASE_URL) instead
of calling Qwen directly, so which model(s)/providers actually serve a
request - Qwen today, an additional provider or the planned Cloudera Agent
Studio workflow later - is decided by config.yaml, not backend code.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

# Deliberately stdlib-only at import time — see backend/app_cai_backend.py
# for why (this file's venv bootstrap runs before third-party packages
# are guaranteed to be installed).

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(line_buffering=True)


_REPO_MARKER = os.path.join("litellm", "config.yaml")


def _looks_like_repo_root(path: str) -> bool:
    return os.path.isfile(os.path.join(path, _REPO_MARKER))


def resolve_repo_root() -> str:
    """Same resolution strategy as the backend/frontend entrypoints: CAI can
    execute this as interpreter code with __file__ unset, and
    CDSW_PROJECT_DIR is not guaranteed to point at the git checkout itself —
    search it (and one level of subfolders) plus cwd (and its subfolders)
    for this repo's own marker file."""
    candidates = []
    project_dir = os.getenv("CDSW_PROJECT_DIR")
    if project_dir and os.path.isdir(project_dir):
        candidates.append(project_dir)
        candidates.extend(
            os.path.join(project_dir, name)
            for name in sorted(os.listdir(project_dir))
            if os.path.isdir(os.path.join(project_dir, name))
        )
    cwd = os.getcwd()
    candidates.append(cwd)
    if os.path.isdir(cwd):
        candidates.extend(
            os.path.join(cwd, name)
            for name in sorted(os.listdir(cwd))
            if os.path.isdir(os.path.join(cwd, name))
        )

    for candidate in candidates:
        if _looks_like_repo_root(candidate):
            return candidate

    if project_dir and os.path.isdir(project_dir):
        return project_dir
    return cwd


REPO_ROOT = resolve_repo_root()
LITELLM_DIR = os.path.join(REPO_ROOT, "litellm")
CONFIG_PATH = os.path.join(LITELLM_DIR, "config.yaml")
VENV_DIR = os.path.join(LITELLM_DIR, ".venv-litellm")
VENV_MARKER = os.path.join(VENV_DIR, ".requirements-installed")
REQUIREMENTS_FILE = os.path.join(LITELLM_DIR, "requirements.txt")

if not os.path.isfile(CONFIG_PATH):
    raise RuntimeError(f"litellm/config.yaml not found at {CONFIG_PATH} — checkout may be incomplete.")


def ensure_venv() -> str:
    venv_python = os.path.join(VENV_DIR, "bin", "python")
    if not os.path.isfile(venv_python):
        print("[litellm] Creating virtualenv at", VENV_DIR)
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])

    requirements_mtime = os.path.getmtime(REQUIREMENTS_FILE) if os.path.isfile(REQUIREMENTS_FILE) else 0
    marker_mtime = os.path.getmtime(VENV_MARKER) if os.path.isfile(VENV_MARKER) else 0
    if requirements_mtime > marker_mtime:
        print("[litellm] Installing litellm proxy dependencies into", VENV_DIR)
        pip_env = os.environ.copy()
        pip_env.pop("PIP_USER", None)
        pip_env.pop("PYTHONUSERBASE", None)
        subprocess.check_call([venv_python, "-m", "pip", "--isolated", "install", "--no-user", "--upgrade", "pip"], env=pip_env)
        subprocess.check_call([venv_python, "-m", "pip", "--isolated", "install", "--no-user", "-r", REQUIREMENTS_FILE], env=pip_env)
        with open(VENV_MARKER, "w") as handle:
            handle.write("ok")

    return venv_python


PYTHON_BIN = ensure_venv()

APP_PORT = os.getenv("CDSW_APP_PORT") or os.getenv("PORT") or "4000"
STARTUP_TIMEOUT = int(os.getenv("LITELLM_STARTUP_TIMEOUT", "60"))
POLL_INTERVAL = 2

if not os.getenv("QWEN_BASE_URL"):
    print("[litellm] WARNING: QWEN_BASE_URL is not set — the commercial-intelligence "
          "model group will fail until it is configured on this Application.")

print("=" * 60)
print("Tempo Scan Commercial Intelligence - LiteLLM Router")
print("=" * 60)
print("Repo root         :", REPO_ROOT)
print("Config            :", CONFIG_PATH)
print("Application port  :", APP_PORT, "(binds 127.0.0.1 — CAI's proxy exposes it externally)")
print("Agent Studio route:", "configured" if os.getenv("AGENT_STUDIO_BASE_URL") else "not provisioned yet (falls back to commercial-intelligence)")
print("=" * 60)
print()


def wait_for_http(url: str, label: str, timeout_seconds: int) -> None:
    start = time.time()
    while True:
        elapsed = int(time.time() - start)
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    print(f"[litellm] [{elapsed}s] {label} ready ({url})")
                    return
        except (urllib.error.URLError, OSError):
            pass
        if elapsed >= timeout_seconds:
            raise RuntimeError(f"{label} did not become healthy at {url} within {timeout_seconds}s")
        print(f"[litellm] [{elapsed}s] waiting for {label}...")
        time.sleep(POLL_INTERVAL)


proxy_cmd = [
    PYTHON_BIN, "-m", "litellm",
    "--config", CONFIG_PATH,
    "--host", "127.0.0.1",
    "--port", str(APP_PORT),
]
print("[litellm] Starting:", " ".join(proxy_cmd))
proxy_process = subprocess.Popen(proxy_cmd, cwd=LITELLM_DIR, env=os.environ.copy())
print("[litellm] PID:", proxy_process.pid)

wait_for_http(f"http://127.0.0.1:{APP_PORT}/health/liveliness", "LiteLLM proxy", STARTUP_TIMEOUT)

print()
print("=" * 60)
print("Tempo Scan LiteLLM Router ready")
print("=" * 60)
print()

try:
    while True:
        return_code = proxy_process.poll()
        if return_code is not None:
            raise RuntimeError(f"LiteLLM proxy exited with code {return_code}")
        time.sleep(5)

except KeyboardInterrupt:
    print("[litellm] Application interrupted.")

finally:
    print()
    print("[litellm] Stopping application process...")
    if proxy_process.poll() is None:
        proxy_process.terminate()
        try:
            proxy_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proxy_process.kill()
    print("[litellm] Application stopped.")
