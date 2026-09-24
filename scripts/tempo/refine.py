#!/usr/bin/env python3
"""Raw MTPL files → datasets/refine/parquet."""

from __future__ import annotations

import argparse
import json
import tempfile
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pandas as pd

from _config import (
    CONFIG_PATH,
    ensure_output_dirs,
    iter_domains,
    load_config,
    resolve_raw_root,
)
from parquet_io import combine_parquet, write_parquet
from transforms import apply_scale_div100, convert_excel_date_columns
from transforms.sap_txt import iter_sap_txt_chunks


def _read_xlsx(path: Path, sheet: str | None = None, header_row: int = 0) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=0 if sheet in (None, "null") else sheet,
        header=header_row,
        dtype=str,
    )
    from transforms.column_map import normalize_columns

    df = normalize_columns(df)
    df = convert_excel_date_columns(df)
    df["_source_file"] = path.name
    df["_loaded_at"] = datetime.now(timezone.utc).isoformat()
    return df


def refine_domain(domain_name: str, config: dict, raw_root: Path, refine_dir: Path) -> dict:
    domains = {spec.name: (spec, files) for spec, files in iter_domains(config, raw_root)}
    if domain_name not in domains:
        raise KeyError(f"Unknown domain '{domain_name}'")

    spec, files = domains[domain_name]
    if not files:
        raise FileNotFoundError(f"No source files found for domain '{domain_name}'")
    scale_cfg = config.get("transforms", {}).get("scale_div100", {})
    output_path = refine_dir / spec.output
    total_rows = 0
    all_columns: list[str] = []

    if spec.format == "sap_txt":
        sap_cfg = config.get("sap_txt", {})
        with tempfile.TemporaryDirectory(prefix=f"tempo-{domain_name}-") as temp_dir:
            parts: list[Path] = []
            part_number = 0
            for source_path in files:
                for frame in iter_sap_txt_chunks(
                    source_path,
                    skip_header_rows=int(sap_cfg.get("skip_header_rows", 3)),
                    delimiter=str(sap_cfg.get("delimiter", "\t")),
                    encoding=str(sap_cfg.get("encoding", "utf-8")),
                    chunk_size=int(sap_cfg.get("chunk_size", 100_000)),
                ):
                    if scale_cfg.get("enabled"):
                        frame = apply_scale_div100(frame, list(scale_cfg.get("columns") or []))
                    total_rows += len(frame)
                    all_columns = list(dict.fromkeys([*all_columns, *frame.columns]))
                    part_path = Path(temp_dir) / f"part-{part_number:05d}.parquet"
                    write_parquet(frame, part_path)
                    parts.append(part_path)
                    part_number += 1
            combine_parquet(parts, output_path)
    elif spec.format == "xlsx":
        frames = [_read_xlsx(path, spec.sheet, spec.header_row) for path in files]
        combined = pd.concat(frames, ignore_index=True, sort=False)
        total_rows = len(combined)
        all_columns = list(combined.columns)
        write_parquet(combined, output_path)
    else:
        raise ValueError(f"Unsupported format '{spec.format}' for domain '{domain_name}'")

    return {
        "domain": domain_name,
        "output": str(output_path.relative_to(refine_dir.parent.parent)),
        "source_files": [path.name for path in files],
        "rows": int(total_rows),
        "columns": all_columns,
    }


def export_transform_rules(config: dict, raw_root: Path, manifest_dir: Path) -> None:
    ref = config.get("reference_only", {}).get("transform_rules")
    if not ref:
        return
    from _config import resolve_domain_files

    files = resolve_domain_files(raw_root, ref)
    if not files:
        print("WARN: transform rules reference file not found, skipping")
        return
    df = _read_xlsx(files[0])
    out = manifest_dir / ref.get("output_json", "transform_rules.json")
    payload = {"source_file": files[0].name, "rows": int(len(df)), "columns": list(df.columns), "data": df.to_dict(orient="records")}
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_manifest(records: list[dict], manifest_dir: Path) -> Path:
    path = manifest_dir / "refine_manifest.json"
    merged = {record["domain"]: record for record in records}
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        for record in previous.get("domains", []):
            merged.setdefault(record["domain"], record)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domains": list(merged.values()),
    }
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refine Tempo MTPL raw files to parquet")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--domain", action="append", help="Domain name from config.yaml (repeatable)")
    parser.add_argument("--list-domains", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    raw_root = resolve_raw_root(config)
    paths = ensure_output_dirs(config)
    refine_dir = paths["refine"]
    manifest_dir = paths["manifest"]

    if args.list_domains:
        for spec, files in iter_domains(config, raw_root):
            status = "ready" if files else "missing"
            print(f"{spec.name}: {status} ({len(files)} file(s))")
        return 0

    if not raw_root.exists():
        print(f"ERROR: raw data not found at {raw_root}", file=sys.stderr)
        print("Copy source files to datasets/raw/ first.", file=sys.stderr)
        return 1

    selected = args.domain or [spec.name for spec, _ in iter_domains(config, raw_root)]
    records: list[dict] = []
    for domain_name in selected:
        print(f"Refining {domain_name}...")
        record = refine_domain(domain_name, config, raw_root, refine_dir)
        records.append(record)
        print(f"  → {record['output']} ({record['rows']:,} rows)")

    export_transform_rules(config, raw_root, manifest_dir)
    manifest_path = write_manifest(records, manifest_dir)
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
