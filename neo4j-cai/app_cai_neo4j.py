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


def resolve_repo_root() -> Path:
    candidates: list[Path] = []
    project_dir = os.getenv("CDSW_PROJECT_DIR")
    if project_dir:
        candidates.append(Path(project_dir))
    candidates.append(Path.cwd())
    script_file = globals().get("__file__")
    if script_file:
        candidates.append(Path(script_file).resolve().parent.parent)
    for base in candidates:
        if (base / "backend" / "app" / "main.py").is_file():
            return base.resolve()
    raise RuntimeError("Could not locate repo root (need backend/app/main.py)")


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
