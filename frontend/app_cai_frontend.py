"""Cloudera AI Application entrypoint for the "Tempo Scan Frontend" application.

Follows the CAI Application execution model: no reliance on __file__, and
CAI's own reverse proxy handles external exposure — Next.js binds
127.0.0.1 only, never 0.0.0.0.

Validates configuration, builds the production Next.js bundle (which bakes
NEXT_PUBLIC_BACKEND_API_URL in at build time), starts it as a child process,
and monitors it. Preserves the child's stdout/stderr so failures show up in
CAI's Application Logs.

Does NOT start the backend or the Mock Market API — see
backend/app_cai_backend.py for the separate "Tempo Scan Backend" CAI
Application entrypoint.
"""
from __future__ import annotations

import os
import subprocess
import time


def resolve_frontend_dir() -> str:
    """CAI can execute this entrypoint as interpreter code where __file__ is
    unset or wrong. Resolve the frontend checkout dir from CDSW_PROJECT_DIR
    first (repo_root/frontend), falling back to the current working
    directory (assumed to already be the frontend dir when run locally)."""
    project_dir = os.getenv("CDSW_PROJECT_DIR")
    if project_dir and os.path.isdir(project_dir):
        candidate = os.path.join(project_dir, "frontend")
        if os.path.isdir(candidate):
            return candidate
    return os.getcwd()


FRONTEND_DIR = resolve_frontend_dir()

# CDSW_APP_PORT is authoritative when CAI sets it; PORT is the generic
# fallback; 3000 is only for ad hoc local testing outside CAI.
APP_PORT = os.getenv("CDSW_APP_PORT") or os.getenv("PORT") or "3000"
BUILD_SKIP = os.getenv("BUILD_SKIP", "0") == "1"

BACKEND_URL = os.getenv("NEXT_PUBLIC_BACKEND_API_URL", "")
if not BACKEND_URL:
    raise RuntimeError(
        "NEXT_PUBLIC_BACKEND_API_URL is required — set it to the deployed "
        "Tempo Scan Backend Application's public URL before building."
    )
if not (BACKEND_URL.startswith("http://") or BACKEND_URL.startswith("https://")):
    raise RuntimeError(f"NEXT_PUBLIC_BACKEND_API_URL must start with http:// or https:// (got: {BACKEND_URL})")

print("=" * 60)
print("Tempo Scan Commercial Intelligence - Frontend")
print("=" * 60)
print("Frontend directory:", FRONTEND_DIR)
print("Application port  :", APP_PORT, "(binds 127.0.0.1 — CAI's proxy exposes it externally)")
print("Backend URL       :", BACKEND_URL)
print("=" * 60)
print()

# =========================================================
# 1. Install dependencies (a fresh CAI checkout has no node_modules)
# =========================================================
if not os.path.isdir(os.path.join(FRONTEND_DIR, "node_modules")):
    print("[frontend] Installing dependencies (npm ci)...")
    install_result = subprocess.run(["npm", "ci"], cwd=FRONTEND_DIR, env=os.environ.copy())
    if install_result.returncode != 0:
        raise RuntimeError(f"npm ci failed with exit code {install_result.returncode}")

# =========================================================
# 2. Build (NEXT_PUBLIC_* is inlined at build time, not read at runtime)
# =========================================================
has_existing_build = os.path.isdir(os.path.join(FRONTEND_DIR, ".next"))
if BUILD_SKIP and has_existing_build:
    print("[frontend] BUILD_SKIP=1 and .next already exists - reusing existing build.")
else:
    print("[frontend] Building production frontend (bakes NEXT_PUBLIC_BACKEND_API_URL into the bundle)...")
    build_result = subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, env=os.environ.copy())
    if build_result.returncode != 0:
        raise RuntimeError(f"Frontend build failed with exit code {build_result.returncode}")

# =========================================================
# 3. Start Next.js production server (this Application's listener, 127.0.0.1)
# =========================================================
start_cmd = ["npx", "next", "start", "-H", "127.0.0.1", "-p", str(APP_PORT)]
print("[frontend] Starting:", " ".join(start_cmd))
# stdout/stderr inherited (not redirected) so failures surface in CAI's Application Logs.
frontend_process = subprocess.Popen(start_cmd, cwd=FRONTEND_DIR, env=os.environ.copy())
print("[frontend] PID:", frontend_process.pid)
print()

try:
    while True:
        return_code = frontend_process.poll()
        if return_code is not None:
            raise RuntimeError(f"Frontend exited with code {return_code}")
        time.sleep(5)

except KeyboardInterrupt:
    print("[frontend] Application interrupted.")

finally:
    print()
    print("[frontend] Stopping application process...")
    if frontend_process.poll() is None:
        frontend_process.terminate()
        try:
            frontend_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            frontend_process.kill()
    print("[frontend] Application stopped.")
