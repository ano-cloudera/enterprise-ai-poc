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
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

# Line-buffer stdout/stderr so print() output shows up in CAI's Application
# Logs immediately rather than sitting in a block buffer for minutes. CAI
# can run this entrypoint two different ways: as a plain script (regular
# TextIOWrapper, which supports reconfigure()) or as Jupyter kernel cells
# (ipykernel's OutStream, which does not) — guard against the latter.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(line_buffering=True)

# Node.js LTS version bundled for CAI runtimes that have no Node.js of their
# own (the PBJ Workbench / JupyterLab Python images are Python-only). Pinned
# so builds are reproducible; bump deliberately, not silently.
NODE_VERSION = "20.18.1"


def _looks_like_frontend_dir(path: str) -> bool:
    return os.path.isfile(os.path.join(path, "package.json")) and os.path.isdir(os.path.join(path, "src"))


def resolve_frontend_dir() -> str:
    """CAI can execute this entrypoint as interpreter code where __file__ is
    unset or wrong, and CDSW_PROJECT_DIR can point at the CAI *project*
    directory rather than the git checkout itself when the repo was added
    as a subfolder (e.g. /home/cdsw/enterprise-ai-poc rather than
    /home/cdsw) — so "<CDSW_PROJECT_DIR>/frontend" alone is not reliable.
    Resolve by looking for this app's own marker files (package.json + src),
    checking <CDSW_PROJECT_DIR>/frontend and <CDSW_PROJECT_DIR>/*/frontend,
    then the current working directory and <cwd>/frontend."""
    candidates = []
    project_dir = os.getenv("CDSW_PROJECT_DIR")
    if project_dir and os.path.isdir(project_dir):
        candidates.append(os.path.join(project_dir, "frontend"))
        candidates.extend(
            os.path.join(project_dir, name, "frontend")
            for name in sorted(os.listdir(project_dir))
            if os.path.isdir(os.path.join(project_dir, name))
        )
    cwd = os.getcwd()
    candidates.append(cwd)
    candidates.append(os.path.join(cwd, "frontend"))

    for candidate in candidates:
        if os.path.isdir(candidate) and _looks_like_frontend_dir(candidate):
            return candidate

    # Nothing matched the marker files — fall back to the old behavior
    # rather than failing outright, since npm ci/build will still fail
    # with a clear message if this guess is wrong.
    if project_dir and os.path.isdir(os.path.join(project_dir, "frontend")):
        return os.path.join(project_dir, "frontend")
    return cwd


FRONTEND_DIR = resolve_frontend_dir()
NODE_INSTALL_DIR = os.path.join(FRONTEND_DIR, ".node-runtime")


def _node_arch() -> str:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    raise RuntimeError(f"Unsupported CPU architecture for portable Node.js download: {machine}")


def ensure_node_bin_dir() -> str:
    """Return a directory containing node/npm/npx, downloading a portable
    Node.js build if the CAI runtime image doesn't already have one (the
    PBJ Workbench / JupyterLab Python images are Python-only — there is no
    guarantee npm is on PATH). Mirrors the native-binary launcher pattern:
    cache under the app directory, probe before trusting it, never assume
    the interpreter's environment has what a Node app needs."""
    if shutil.which("npm") and shutil.which("node"):
        print("[frontend] Using system Node.js:", shutil.which("node"))
        return os.path.dirname(shutil.which("node"))

    arch = _node_arch()
    dist_name = f"node-v{NODE_VERSION}-linux-{arch}"
    node_home = os.path.join(NODE_INSTALL_DIR, dist_name)
    bin_dir = os.path.join(node_home, "bin")
    node_bin = os.path.join(bin_dir, "node")

    if os.path.isfile(node_bin):
        print("[frontend] Reusing cached portable Node.js at", node_home)
        return bin_dir

    os.makedirs(NODE_INSTALL_DIR, exist_ok=True)
    archive_name = f"{dist_name}.tar.xz"
    url = f"https://nodejs.org/dist/v{NODE_VERSION}/{archive_name}"
    archive_path = os.path.join(NODE_INSTALL_DIR, archive_name)

    print(f"[frontend] No system Node.js found. Downloading portable Node.js {NODE_VERSION} ({arch})...")
    print("[frontend]", url)
    urllib.request.urlretrieve(url, archive_path)

    with tarfile.open(archive_path, mode="r:xz") as archive:
        archive.extractall(NODE_INSTALL_DIR)
    os.remove(archive_path)

    if not os.path.isfile(node_bin):
        raise RuntimeError(f"Portable Node.js download did not produce an executable at {node_bin}")

    # Probe the binary actually runs before trusting it for the real build.
    subprocess.run([node_bin, "--version"], check=True)
    print("[frontend] Portable Node.js ready at", node_home)
    return bin_dir

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
# 0. Ensure Node.js/npm are available (the PBJ Workbench / JupyterLab
#    Python runtime images have no Node.js of their own)
# =========================================================
node_bin_dir = ensure_node_bin_dir()
run_env = os.environ.copy()
run_env["PATH"] = f"{node_bin_dir}{os.pathsep}{run_env.get('PATH', '')}"

# =========================================================
# 1. Install dependencies (a fresh CAI checkout has no node_modules)
# =========================================================
if not os.path.isdir(os.path.join(FRONTEND_DIR, "node_modules")):
    print("[frontend] Installing dependencies (npm ci)...")
    install_result = subprocess.run(["npm", "ci"], cwd=FRONTEND_DIR, env=run_env)
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
    build_result = subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, env=run_env)
    if build_result.returncode != 0:
        raise RuntimeError(f"Frontend build failed with exit code {build_result.returncode}")

# =========================================================
# 3. Start Next.js production server (this Application's listener, 127.0.0.1)
# =========================================================
start_cmd = ["npx", "next", "start", "-H", "127.0.0.1", "-p", str(APP_PORT)]
print("[frontend] Starting:", " ".join(start_cmd))
# stdout/stderr inherited (not redirected) so failures surface in CAI's Application Logs.
frontend_process = subprocess.Popen(start_cmd, cwd=FRONTEND_DIR, env=run_env)
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
