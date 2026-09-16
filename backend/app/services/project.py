from __future__ import annotations

import yaml
from app.core.config import get_settings


def load_project_config() -> dict:
    settings = get_settings()
    path = settings.project_dir / "config.yaml"
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
