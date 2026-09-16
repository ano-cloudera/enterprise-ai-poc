from __future__ import annotations

from threading import RLock
import yaml

from app.core.config import get_settings


class RuntimeSettingsStore:
    def __init__(self) -> None:
        settings = get_settings()
        project_path = settings.project_dir / "config.yaml"
        project = {}
        if project_path.exists():
            with project_path.open("r", encoding="utf-8") as handle:
                project = yaml.safe_load(handle) or {}
        self._lock = RLock()
        self._data = {
            "language": "auto",
            "system_prompt": project.get("system_prompt", ""),
            "model_name": settings.qwen_model,
        }

    def get(self) -> dict:
        with self._lock:
            return dict(self._data)

    def update(self, values: dict) -> dict:
        with self._lock:
            for key in ("language", "system_prompt", "model_name"):
                if key in values and values[key] is not None:
                    self._data[key] = values[key]
            return dict(self._data)


runtime_settings = RuntimeSettingsStore()
