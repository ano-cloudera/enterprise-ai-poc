from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings, get_settings
from app.db.base import BackendExecutionContext
from app.db.factory import get_data_backend

from .registry import TempoOssieRegistry


Scalar = str | int | float | bool


class OssieQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, list[Scalar]] = Field(default_factory=dict)
    start_calmonth: int | None = Field(default=None, ge=200001, le=299912)
    end_calmonth: int | None = Field(default=None, ge=200001, le=299912)
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=1000)


class OssieResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)


class OssieJoinPathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    dimensions: list[str] = Field(default_factory=list)


def _literal(value: Scalar) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + value.replace("'", "''") + "'"


class TempoOssieService:
    """Deterministic single-dataset compiler and optional Impala executor."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        project_dir = self.settings.project_root / self.settings.ossie_project_id
        self.registry = TempoOssieRegistry(project_dir)

    @property
    def enabled(self) -> bool:
        return self.settings.semantic_execution_mode == "ossie"

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "execution_mode": self.settings.semantic_execution_mode,
            "project_id": self.settings.ossie_project_id,
            "data_backend": self.settings.data_backend,
            "model": self.registry.model["name"],
            "datasets": len(self.registry.datasets),
            "metrics": len(self.registry.metrics),
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "status": "ok",
            **self.status(),
            **self.registry.capability_summary(),
        }

    def resolve(self, question: str) -> dict[str, Any]:
        return self.registry.resolve_metric(question)

    def get_metric_definition(self, metric_name: str) -> dict[str, Any]:
        return self.registry.metric_definition(metric_name)

    def find_join_path(self, metric_name: str, dimensions: list[str]) -> dict[str, Any]:
        definition = self.registry.metric_definition(metric_name)
        allowed = set(definition["allowed_dimensions"])
        requested = set(dimensions)
        unsupported = requested - allowed
        if unsupported:
            return {
                "status": "unsupported",
                "reason": "dimensions_not_available_on_governed_dataset",
                "metric": metric_name,
                "unsupported_dimensions": sorted(unsupported),
                "instruction": "Extend the semantic contract; do not invent a join.",
            }
        dataset = definition["base_dataset"]
        return {
            "status": "success",
            "metric": metric_name,
            "dimensions": dimensions,
            "path": [dataset],
            "joins": [],
            "source_view": self.registry.datasets[dataset]["source"],
            "instruction": "Single governed dataset; no runtime join required.",
        }

    def query_ontology(self, question: str) -> dict[str, Any]:
        resolution = self.resolve(question)
        if resolution.get("status") != "resolved":
            return resolution
        definition = resolution["definition"]
        dataset_name = definition["base_dataset"]
        dataset = self.registry.datasets[dataset_name]
        return {
            "status": "success",
            "semantic_layer": "Apache Ossie Core",
            "resolved_metric": definition,
            "business_object": {
                "dataset": dataset_name,
                "description": dataset.get("description"),
                "source_view": dataset.get("source"),
                "grain": self.registry.tempo_extension(dataset).get("grain"),
                "ai_context": dataset.get("ai_context", {}),
            },
            "note": (
                "Core semantic context only. PuppyGraph and a relationship "
                "ontology are intentionally deferred."
            ),
        }

    def compile_query(self, request: OssieQueryRequest) -> dict[str, Any]:
        definition = self.registry.metric_definition(request.metric)
        dataset_name = definition["base_dataset"]
        dataset = self.registry.datasets[dataset_name]
        fields = self.registry.dataset_fields[dataset_name]
        allowed_dimensions = set(definition["allowed_dimensions"])
        requested_dimensions = list(dict.fromkeys(request.dimensions))

        unknown_dimensions = set(requested_dimensions) - allowed_dimensions
        if unknown_dimensions:
            raise ValueError(
                f"Metric {request.metric} does not allow dimensions "
                f"{sorted(unknown_dimensions)}"
            )

        for field_name in request.filters:
            if field_name not in allowed_dimensions:
                raise ValueError(f"Filter is not governed for this metric: {field_name}")
            if field_name not in fields:
                raise ValueError(f"Unknown filter field: {field_name}")

        expression = definition["expression"].replace(f"{dataset_name}.", "d.")
        projections = [f"d.{dimension} AS {dimension}" for dimension in requested_dimensions]
        projections.append(f"{expression} AS metric_value")

        predicates: list[str] = []
        for field_name in definition["required_filters"]:
            if field_name not in fields:
                raise ValueError(f"Unknown required filter: {field_name}")
            predicates.append(f"d.{field_name} = TRUE")
        if definition["row_filter"]:
            predicates.append(f"({definition['row_filter']})")
        for field_name, values in request.filters.items():
            if not values:
                raise ValueError(f"Filter values cannot be empty: {field_name}")
            rendered = ", ".join(_literal(value) for value in values)
            predicates.append(f"d.{field_name} IN ({rendered})")

        has_calmonth = "calmonth" in fields
        if request.start_calmonth is not None or request.end_calmonth is not None:
            if not has_calmonth:
                raise ValueError(f"Dataset {dataset_name} has no calmonth field")
            if request.start_calmonth is not None:
                predicates.append(f"d.calmonth >= {request.start_calmonth}")
            if request.end_calmonth is not None:
                predicates.append(f"d.calmonth <= {request.end_calmonth}")

        query = [
            "SELECT",
            "  " + ",\n  ".join(projections),
            f"FROM {dataset['source']} d",
        ]
        if predicates:
            query.append("WHERE " + "\n  AND ".join(predicates))
        if requested_dimensions:
            query.append(
                "GROUP BY "
                + ", ".join(f"d.{dimension}" for dimension in requested_dimensions)
            )
        query.append(f"ORDER BY metric_value {request.order.upper()}")
        limit = min(request.limit, self.settings.ossie_max_rows)
        query.append(f"LIMIT {limit}")
        sql = "\n".join(query)

        return {
            "status": "compiled",
            "sql": sql,
            "semantic_plan": {
                "metric": request.metric,
                "metric_id": definition["metric_id"],
                "dataset": dataset_name,
                "source_view": dataset["source"],
                "dimensions": requested_dimensions,
                "filters": request.filters,
                "grain": self.registry.tempo_extension(dataset).get("grain"),
                "governance_status": definition["governance_status"],
                "business_approval_status": definition["business_approval_status"],
                "original_kpi_id": definition["original_kpi_id"],
            },
        }

    def execute_query(
        self,
        request: OssieQueryRequest,
        *,
        trace_id: str = "",
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("OSSIE_SEMANTIC_MODE_DISABLED")
        if self.settings.data_backend != "impala":
            raise RuntimeError("OSSIE_REQUIRES_IMPALA_BACKEND")
        compiled = self.compile_query(request)
        result = get_data_backend().execute(
            compiled["sql"],
            BackendExecutionContext(trace_id=trace_id, purpose="ossie_governed_query"),
        )
        return {
            **compiled,
            "status": "success",
            "columns": [column.name for column in result.columns],
            "rows": result.records(),
            "row_count": result.row_count,
            "telemetry": result.telemetry.model_dump(by_alias=True),
        }


@lru_cache(maxsize=1)
def get_tempo_ossie_service() -> TempoOssieService:
    return TempoOssieService()

