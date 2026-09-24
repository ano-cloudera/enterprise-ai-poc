from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


@dataclass(frozen=True)
class DomainSpec:
    name: str
    output: str
    format: str
    files: tuple[str, ...]
    sheet: str | None = None
    header_row: int = 0


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve_path(config: dict[str, Any], key: str) -> Path:
    return (ROOT / config["paths"][key]).resolve()


def resolve_raw_root(config: dict[str, Any]) -> Path:
    primary = resolve_path(config, "raw")
    if primary.exists():
        return primary
    fallback = resolve_path(config, "raw_fallback")
    if fallback.exists():
        return fallback
    return primary


def resolve_domain_files(raw_root: Path, domain: dict[str, Any]) -> list[Path]:
    candidates: list[str] = list(domain.get("files") or [])
    legacy: list[str] = list(domain.get("legacy_files") or [])
    for rel in candidates:
        path = raw_root / rel
        if path.exists():
            return [raw_root / item for item in candidates if (raw_root / item).exists()]
    return [raw_root / item for item in legacy if (raw_root / item).exists()]


def iter_domains(config: dict[str, Any], raw_root: Path) -> list[tuple[DomainSpec, list[Path]]]:
    domains: list[tuple[DomainSpec, list[Path]]] = []
    for name, spec in (config.get("domains") or {}).items():
        files = resolve_domain_files(raw_root, spec)
        domains.append(
            (
                DomainSpec(
                    name=name,
                    output=spec["output"],
                    format=spec["format"],
                    files=tuple(spec.get("files") or ()),
                    sheet=spec.get("sheet"),
                    header_row=int(spec.get("header_row", 0)),
                ),
                files,
            )
        )
    return domains


def ensure_output_dirs(config: dict[str, Any]) -> dict[str, Path]:
    keys = ("refine", "csv_sample", "manifest", "gold", "qa")
    paths = {key: resolve_path(config, key) for key in keys}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
