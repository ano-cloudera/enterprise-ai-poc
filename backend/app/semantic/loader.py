from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import yaml

from app.core.config import get_settings
from app.semantic.models import SemanticProject


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Semantic config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=8)
def load_semantic_project(project_id: str | None = None) -> SemanticProject:
    settings = get_settings()
    project_id = project_id or settings.project_id
    base = settings.project_root / project_id / "semantic"
    manifest = _read_yaml(base / "manifest.yaml")
    datasets: dict[str, dict] = {}
    for filename in manifest.get("dataset_files", []):
        raw = _read_yaml(base / filename)
        datasets[raw["name"]] = raw
    terms = _read_yaml(base / manifest.get("business_terms_file", "business_terms.yaml"))
    resolution = {}
    if manifest.get("resolution_file"):
        resolution = _read_yaml(base / manifest["resolution_file"]).get("resolution", {})
    golden_questions = []
    if manifest.get("golden_questions_file"):
        golden_questions = _read_yaml(base / manifest["golden_questions_file"]).get("golden_questions", [])
    forecast_golden_questions = []
    if manifest.get("forecast_golden_questions_file"):
        forecast_golden_questions = _read_yaml(base / manifest["forecast_golden_questions_file"]).get("forecast_golden_questions", [])
    weather_golden_questions = []
    if manifest.get("weather_golden_questions_file"):
        weather_golden_questions = _read_yaml(base / manifest["weather_golden_questions_file"]).get("weather_golden_questions", [])
    market_golden_questions = []
    if manifest.get("market_golden_questions_file"):
        market_golden_questions = _read_yaml(base / manifest["market_golden_questions_file"]).get("market_golden_questions", [])
    return SemanticProject(
        project=project_id,
        datasets=datasets,
        business_terms=terms.get("business_terms", {}),
        allowed_questions=manifest.get("allowed_questions", []),
        resolution=resolution,
        golden_questions=golden_questions,
        forecast_golden_questions=forecast_golden_questions,
        weather_golden_questions=weather_golden_questions,
        market_golden_questions=market_golden_questions,
    )


def semantic_prompt_context(project: SemanticProject) -> str:
    parts: list[str] = [f"PROJECT: {project.project}"]
    for name, dataset in project.datasets.items():
        parts.append(f"\nDATASET {name}: {dataset.source}")
        if dataset.description:
            parts.append(dataset.description)
        if dataset.metrics:
            parts.append("Metrics:")
            for key, metric in dataset.metrics.items():
                aliases = ", ".join(metric.aliases)
                parts.append(f"- {key}: {metric.aggregation}({metric.expression}); aliases=[{aliases}]")
        if dataset.dimensions:
            parts.append("Dimensions:")
            for key, dim in dataset.dimensions.items():
                aliases = ", ".join(dim.aliases)
                parts.append(f"- {key}: column={dim.column}; aliases=[{aliases}]")
        if dataset.time_dimensions:
            parts.append("Time dimensions:")
            for key, dim in dataset.time_dimensions.items():
                parts.append(f"- {key}: column={dim.column}; grains={','.join(dim.grains)}")
        if dataset.relationships:
            parts.append("Relationships:")
            for key, rel in dataset.relationships.items():
                parts.append(f"- {key}: dataset={rel.dataset}; type={rel.type}; join={','.join(rel.join)}")
        parts.append(f"Query rules: default_limit={dataset.query_rules.default_limit}; max_limit={dataset.query_rules.max_limit}; require_date_filter={dataset.query_rules.require_date_filter}")
        if dataset.query_rules.allowed_fields:
            parts.append(f"Allowed fields: {','.join(dataset.query_rules.allowed_fields)}")
        for note in dataset.query_rules.notes:
            parts.append(f"Rule: {note}")
    if project.business_terms:
        parts.append("\nBusiness terms:")
        for key, value in project.business_terms.items():
            parts.append(f"- {key}: {value}")
    return "\n".join(parts)


def allowed_tables(project: SemanticProject) -> set[str]:
    return {dataset.source.lower() for dataset in project.datasets.values()}


def allowed_columns(project: SemanticProject) -> set[str]:
    columns: set[str] = set()
    for dataset in project.datasets.values():
        for metric in dataset.metrics.values():
            # Foundation metrics use direct columns. Complex expressions can be expanded later.
            expression = metric.expression.strip()
            if expression.replace("_", "").isalnum():
                columns.add(expression.lower())
        for dimension in dataset.dimensions.values():
            columns.add(dimension.column.lower())
        for time_dimension in dataset.time_dimensions.values():
            columns.add(time_dimension.column.lower())
        columns.update(key.lower() for key in dataset.primary_key)
        columns.update(field.lower() for field in dataset.query_rules.allowed_fields)
    return columns


def governed_table_name(dataset, dialect: str = "duckdb", catalog: str = "", schema: str = "") -> str:
    if dialect != "trino":
        return dataset.source
    mapping = dataset.trino
    table = mapping.table if mapping else dataset.source
    governed_catalog = (mapping.catalog if mapping else None) or catalog
    governed_schema = (mapping.schema if mapping else None) or schema
    if not governed_catalog or not governed_schema:
        raise ValueError("Trino catalog and schema are required for governed table qualification")
    return f"{governed_catalog}.{governed_schema}.{table}"


def table_policies(
    project: SemanticProject,
    dialect: str = "duckdb",
    catalog: str = "",
    schema: str = "",
) -> dict[str, dict]:
    """Return table-scoped SQL policy derived only from validated semantic config."""
    policies: dict[str, dict] = {}
    for dataset_name, dataset in project.datasets.items():
        columns: set[str] = set()
        for metric in dataset.metrics.values():
            expression = metric.expression.strip()
            if expression.replace("_", "").isalnum():
                columns.add(expression.lower())
        columns.update(d.column.lower() for d in dataset.dimensions.values())
        columns.update(d.column.lower() for d in dataset.time_dimensions.values())
        columns.update(c.lower() for c in dataset.primary_key)
        columns.update(c.lower() for c in dataset.query_rules.allowed_fields)
        policies[governed_table_name(dataset, dialect, catalog, schema).lower()] = {
            "dataset": dataset_name,
            "columns": columns,
            "time_columns": {d.column.lower() for d in dataset.time_dimensions.values()},
            "default_limit": dataset.query_rules.default_limit,
            "max_limit": dataset.query_rules.max_limit,
            "require_date_filter": dataset.query_rules.require_date_filter,
            "allowed_functions": {name.lower() for name in dataset.query_rules.allowed_functions},
        }
    return policies


def allowed_relationships(project: SemanticProject) -> set[frozenset[str]]:
    relationships: set[frozenset[str]] = set()
    for name, dataset in project.datasets.items():
        for relationship in dataset.relationships.values():
            relationships.add(frozenset((name, relationship.dataset)))
    return relationships
