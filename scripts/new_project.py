from __future__ import annotations

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new project profile from the reusable template.")
    parser.add_argument("project_id", help="snake_case project id, e.g. bank_sumut")
    args = parser.parse_args()
    source = ROOT / "projects" / "_template"
    target = ROOT / "projects" / args.project_id
    if target.exists():
        raise SystemExit(f"Project already exists: {target}")
    shutil.copytree(source, target)
    print(f"Created {target}")
    print(f"Next: set PROJECT_ID={args.project_id} and edit config/semantic files.")


if __name__ == "__main__":
    main()
