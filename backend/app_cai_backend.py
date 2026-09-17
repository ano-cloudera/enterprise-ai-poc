"""Cloudera AI Application entrypoint for the "Tempo Scan Backend" application.

Follows the CAI Application execution model: no external port binding
assumptions, no reliance on __file__, and CAI's own reverse proxy handles
external exposure — every process here binds 127.0.0.1 only.

Starts the Mock External Market API as an internal child process, waits for
it to become healthy, then starts the FastAPI backend (the Application's
actual listener) and monitors both. Preserves each child's stdout/stderr so
failures show up in CAI's Application Logs.

Does NOT start the Next.js frontend — see frontend/app_cai_frontend.py for
the separate "Tempo Scan Frontend" CAI Application entrypoint.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

# Deliberately stdlib-only at import time: this file's top-level code (venv
# bootstrap, readiness polling) runs under CAI's own interpreter, which may
# not yet have backend/requirements-lock.txt installed. Do not add a
# third-party import above this line.


def resolve_repo_root() -> str:
    """CAI can execute this entrypoint as interpreter code where __file__ is
    unset or wrong. Resolve the checkout root from CDSW_PROJECT_DIR first,
    falling back to the current working directory."""
    project_dir = os.getenv("CDSW_PROJECT_DIR")
    if project_dir and os.path.isdir(project_dir):
        return project_dir
    return os.getcwd()


REPO_ROOT = resolve_repo_root()
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
VENV_DIR = os.path.join(REPO_ROOT, ".venv")
VENV_MARKER = os.path.join(VENV_DIR, ".requirements-installed")
REQUIREMENTS_FILE = os.path.join(BACKEND_DIR, "requirements-lock.txt")


def ensure_venv() -> str:
    """CAI Application slots can be a fresh checkout with no pre-installed
    virtualenv. Bootstrap one under the repo root and install backend
    dependencies into it, rather than assuming sys.executable already has
    them (don't rely on system/interpreter Python having the right packages)."""
    venv_python = os.path.join(VENV_DIR, "bin", "python")
    if not os.path.isfile(venv_python):
        print("[backend] Creating virtualenv at", VENV_DIR)
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])

    requirements_mtime = os.path.getmtime(REQUIREMENTS_FILE) if os.path.isfile(REQUIREMENTS_FILE) else 0
    marker_mtime = os.path.getmtime(VENV_MARKER) if os.path.isfile(VENV_MARKER) else 0
    if requirements_mtime > marker_mtime:
        print("[backend] Installing backend dependencies into", VENV_DIR)
        # Some CAI runtimes force PIP_USER=true, which is invalid inside a venv — strip it.
        pip_env = os.environ.copy()
        pip_env.pop("PIP_USER", None)
        pip_env.pop("PYTHONUSERBASE", None)
        subprocess.check_call([venv_python, "-m", "pip", "--isolated", "install", "--no-user", "--upgrade", "pip"], env=pip_env)
        subprocess.check_call([venv_python, "-m", "pip", "--isolated", "install", "--no-user", "-r", REQUIREMENTS_FILE], env=pip_env)
        with open(VENV_MARKER, "w") as handle:
            handle.write("ok")

    return venv_python


PYTHON_BIN = ensure_venv()

# CDSW_APP_PORT is authoritative when CAI sets it; PORT is the generic
# fallback; 8000 is only for ad hoc local testing outside CAI.
APP_PORT = os.getenv("CDSW_APP_PORT") or os.getenv("PORT") or "8000"
MARKET_API_PORT = os.getenv("MARKET_API_INTERNAL_PORT", "8100")
MARKET_API_STARTUP_TIMEOUT = int(os.getenv("MARKET_API_STARTUP_TIMEOUT", "60"))
BACKEND_STARTUP_TIMEOUT = int(os.getenv("BACKEND_STARTUP_TIMEOUT", "60"))
POLL_INTERVAL = 2

DATA_BACKEND = os.getenv("DATA_BACKEND", "duckdb")
LLM_MODE = os.getenv("LLM_MODE", "mock")

if LLM_MODE == "remote":
    if not os.getenv("QWEN_BASE_URL"):
        raise RuntimeError("QWEN_BASE_URL is required when LLM_MODE=remote (existing Qwen CAI Application URL).")
    if not os.getenv("QWEN_MODEL"):
        raise RuntimeError("QWEN_MODEL is required when LLM_MODE=remote.")

if DATA_BACKEND == "duckdb":
    # The DuckDB backend (app.db.duckdb_backend.DuckDBBackend.initialize)
    # creates runtime/tempo_scan.duckdb itself from these CSV fixtures on
    # its first query — the .duckdb file itself is a generated artifact
    # (gitignored) and is NOT expected to already exist on a fresh CAI
    # checkout. Only the source CSVs, which ARE committed, are required
    # upfront.
    fixtures_dir = os.path.join(REPO_ROOT, "projects", "tempo_scan", "fixtures")
    required_fixtures = ("commercial_sales_daily.csv", "commercial_inventory_daily.csv")
    missing_fixtures = [name for name in required_fixtures if not os.path.isfile(os.path.join(fixtures_dir, name))]
    if missing_fixtures:
        raise RuntimeError(
            f"Missing sample data fixtures in {fixtures_dir}: {', '.join(missing_fixtures)}. "
            "Run scripts/generate_sample_data.py first, or set DATA_BACKEND=trino with Trino credentials."
        )

if not os.getenv("CORS_ORIGINS"):
    print("[backend] WARNING: CORS_ORIGINS is not set. Set it to the deployed "
          "Tempo Scan Frontend Application's public URL once known.")

# The backend's own /api/deployment/readiness check reads MARKET_API_BASE_URL
# from Settings — keep it in sync with the port this entrypoint actually
# starts the Mock Market API on, regardless of what the operator passed in.
os.environ["MARKET_API_BASE_URL"] = f"http://127.0.0.1:{MARKET_API_PORT}"

os.makedirs(os.path.join(REPO_ROOT, "runtime"), exist_ok=True)

print("=" * 60)
print("Tempo Scan Commercial Intelligence - Backend")
print("=" * 60)
print("Repo root         :", REPO_ROOT)
print("Application port  :", APP_PORT, "(binds 127.0.0.1 — CAI's proxy exposes it externally)")
print("Market API port   :", MARKET_API_PORT)
print("Data backend      :", DATA_BACKEND)
print("LLM provider      :", "configured (remote Qwen)" if LLM_MODE == "remote" else "mock")
print("=" * 60)
print()


def wait_for_http(url: str, label: str, timeout_seconds: int) -> None:
    start = time.time()
    while True:
        elapsed = int(time.time() - start)
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    print(f"[backend] [{elapsed}s] {label} ready ({url})")
                    return
        except (urllib.error.URLError, OSError):
            pass
        if elapsed >= timeout_seconds:
            raise RuntimeError(f"{label} did not become healthy at {url} within {timeout_seconds}s")
        print(f"[backend] [{elapsed}s] waiting for {label}...")
        time.sleep(POLL_INTERVAL)


# =========================================================
# 1. Start Mock External Market API (internal child process, 127.0.0.1)
# =========================================================
market_cmd = [
    PYTHON_BIN, "-m", "uvicorn",
    "app.mock_market_api.main:app",
    "--host", "127.0.0.1",
    "--port", MARKET_API_PORT,
]
print("[market-api] Starting:", " ".join(market_cmd))
# stdout/stderr inherited (not redirected) so failures surface in CAI's Application Logs.
market_process = subprocess.Popen(market_cmd, cwd=BACKEND_DIR, env=os.environ.copy())
print("[market-api] PID:", market_process.pid)

wait_for_http(f"http://127.0.0.1:{MARKET_API_PORT}/health", "Mock External Market API", MARKET_API_STARTUP_TIMEOUT)

# =========================================================
# 2. Start FastAPI backend (this Application's listener, 127.0.0.1 only)
# =========================================================
backend_cmd = [
    PYTHON_BIN, "-m", "uvicorn",
    "app.main:app",
    "--host", "127.0.0.1",
    "--port", str(APP_PORT),
    "--app-dir", BACKEND_DIR,
    "--log-level", "info",
]
print("[backend] Starting:", " ".join(backend_cmd))
backend_process = subprocess.Popen(backend_cmd, cwd=REPO_ROOT, env=os.environ.copy())
print("[backend] PID:", backend_process.pid)

wait_for_http(f"http://127.0.0.1:{APP_PORT}/api/health", "Backend API", BACKEND_STARTUP_TIMEOUT)

print()
print("=" * 60)
print("Tempo Scan Backend ready")
print("=" * 60)
print()

# =========================================================
# 3. Monitor both processes; clean up on shutdown
# =========================================================
try:
    while True:
        market_return = market_process.poll()
        if market_return is not None:
            raise RuntimeError(f"Mock External Market API exited with code {market_return}")

        backend_return = backend_process.poll()
        if backend_return is not None:
            raise RuntimeError(f"Backend API exited with code {backend_return}")

        time.sleep(5)

except KeyboardInterrupt:
    print("[backend] Application interrupted.")

finally:
    print()
    print("[backend] Stopping application processes...")

    for name, process in (("backend", backend_process), ("market-api", market_process)):
        if process.poll() is None:
            print(f"[{name}] Stopping...")
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

    print("[backend] Application stopped.")
