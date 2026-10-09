"""Cloudera AI Application entrypoint — Tempo Scan Neo4j Ontology sidecar.

Does not embed a Neo4j server. Point NEO4J_URI at Neo4j Aura, a dedicated VM,
or docker-compose on a host reachable from this application (Bolt TLS as required).

Optional NEO4J_AUTO_SEED=1 runs seed from tempo_domain_graph.yaml on startup.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time


def _is_repo_root(base: Path) -> bool:
    return (base / "backend" / "app" / "main.py").is_file() and (
        base / "neo4j-cai" / "app_cai_neo4j.py"
    ).is_file()


def resolve_repo_root() -> Path:
    """Locate repo root on CAI (same defensive pattern as backend/app_cai_backend.py)."""
    override = (os.getenv("TEMPO_REPO_ROOT") or os.getenv("REPO_ROOT") or "").strip()
    if override:
        root = Path(override).expanduser().resolve()
        if _is_repo_root(root):
            return root

    candidates: list[Path] = []
    project_dir = os.getenv("CDSW_PROJECT_DIR")
    if project_dir:
        base = Path(project_dir)
        candidates.append(base)
        if base.is_dir():
            candidates.extend(path for path in base.iterdir() if path.is_dir())
    cwd = Path.cwd()
    candidates.append(cwd)
    if cwd.is_dir():
        candidates.extend(path for path in cwd.iterdir() if path.is_dir())
    script_file = globals().get("__file__")
    if script_file:
        script_path = Path(script_file).resolve()
        candidates.append(script_path.parent.parent)  # neo4j-cai/.. = repo root
        candidates.append(script_path.parent)  # if layout differs

    seen: set[Path] = set()
    for base in candidates:
        for root in (base, base.parent):
            try:
                resolved = root.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            if _is_repo_root(resolved):
                return resolved

    hint = (
        "Set TEMPO_REPO_ROOT to the git checkout (directory containing backend/ and neo4j-cai/), "
        "or run this file as the CAI Application Script (not pasted notebook cells — __file__ is missing there). "
        f"CDSW_PROJECT_DIR={project_dir!r} cwd={cwd!r}"
    )
    raise RuntimeError(f"Could not locate repo root (need backend/app/main.py). {hint}")


def ensure_venv(repo_root: Path) -> Path:
    venv_dir = repo_root / "neo4j-cai" / ".venv-cai"
    python = venv_dir / "bin" / "python"
    marker = venv_dir / ".requirements-installed"
    req = repo_root / "neo4j-cai" / "requirements.txt"
    backend_req = repo_root / "backend" / "requirements.txt"
    if not python.is_file():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    newest = max(req.stat().st_mtime, backend_req.stat().st_mtime)
    if not marker.exists() or marker.stat().st_mtime < newest:
        env = os.environ.copy()
        env.pop("PIP_USER", None)
        subprocess.check_call([str(python), "-m", "pip", "--isolated", "install", "--no-user", "-r", str(req)], env=env)
        subprocess.check_call(
            [str(python), "-m", "pip", "--isolated", "install", "--no-user", "-r", str(backend_req)],
            env=env,
        )
        marker.write_text("ok\n", encoding="utf-8")
    return python


def main() -> None:
    repo_root = resolve_repo_root()
    port = os.getenv("CDSW_APP_PORT") or os.getenv("PORT") or "7680"
    dry_run = os.getenv("CAI_DRY_RUN") == "1"
    python = Path(sys.executable) if dry_run else ensure_venv(repo_root)
    backend_dir = repo_root / "backend"
    os.environ.setdefault("TEMPO_BACKEND_ROOT", str(backend_dir))
    os.environ["PYTHONPATH"] = str(backend_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")
    command = [
        str(python),
        "-m",
        "uvicorn",
        "app.main:app",
        "--app-dir",
        str(repo_root / "neo4j-cai"),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    if dry_run:
        print(json.dumps({"cwd": str(repo_root), "command": command}))
        return
    print(f"[neo4j-ontology] starting on 127.0.0.1:{port}", flush=True)
    process = subprocess.Popen(command, cwd=repo_root / "neo4j-cai", env=os.environ.copy())
    try:
        while True:
            if process.poll() is not None:
                raise RuntimeError(f"Neo4j ontology app exited with code {process.returncode}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("[neo4j-ontology] interrupted", flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
