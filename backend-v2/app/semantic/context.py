from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
import re

from app.semantic.registry import TempoOssieRegistry
from app.semantic.questions import CURATED_CONTRACTS, QuestionBank


ROOT = Path(__file__).resolve().parents[2]
PROJECT_DIR = ROOT / "projects" / "tempo_scan_impala"


@dataclass(frozen=True)
class TablePolicy:
    name: str
    domain: str
    columns: frozenset[str]
    time_columns: frozenset[str]
    description: str


_DOMAIN_DATASETS = {
    "sales": {
        "monthly_executive", "material_360", "customer_material_360",
        "sales_office_material_360", "sales_office_q4", "service_level_material",
        "service_level_sales_office",
    },
    "b2b": {
        "b2b_branch_estore", "b2b_material_plu", "b2b_customer_branch_estore",
        "b2b_customer_material_plu", "customer_reconciliation",
    },
    "stock_tempo": {"stock_tempo_month", "material_360"},
    "stock_sat_idm": {"sat_idm_dc_month"},
    "sat_oos": {"sat_oos_material_month"},
    "cross_domain": {
        "material_360", "customer_reconciliation", "stock_tempo_sales_material_month",
        "sales_b2b_material_month", "b2b_satidm_branch_month", "satidm_oos_material_month",
    },
}

_CONCEPT_PATTERNS = {
    "sell_in": ("sell-in", "sell in"),
    "sell_out": ("sell-out", "sell out"),
    "stock_tempo": ("stock tempo", "stok tempo", "gudang tempo"),
    "dc_stock": ("dc stock", "dcstock", "stok dc"),
    "store_stock": ("store stock", "storestock", "stok store"),
    "oos": ("oos", "out of stock"),
    "service_level": ("service level", "fill rate"),
}

_GUIDANCE_TOPICS = {
    "sales": ("sales",),
    "stock": ("stock_tempo", "stock_sat_idm"),
    "oos": ("sat_oos",),
    "b2b": ("b2b",),
}

_GUIDANCE_DOMAIN_OPTIONS = (
    {"name": "Sales / Sell-In", "metrics": ["gross_billing_value"], "examples": ["Berapa Gross Sales TEMPO selama Q4 2024?"]},
    {"name": "B2B / Sell-Out", "metrics": ["b2b_branch_sell_out_value"], "examples": ["Branch mana dengan nilai Sell-Out terbesar?"]},
    {"name": "Stock Tempo", "metrics": ["stock_tempo_total_qty"], "examples": ["Bagaimana tren stok gudang Tempo per bulan?"]},
    {
        "name": "Stock SAT-IDM",
        "metrics": ["sat_idm_dc_stock_quantity", "sat_idm_store_stock_quantity"],
        "examples": ["Berapa stok DC partner atau stok retail per division?"],
    },
    {"name": "SAT OOS", "metrics": ["sat_oos_rate"], "examples": ["Material mana dengan SAT OOS rate tertinggi?"]},
    {"name": "Service Level", "metrics": ["service_fill_rate"], "examples": ["Material mana dengan Fill Rate terendah?"]},
    {"name": "Picking", "metrics": ["average_picking_minutes"], "examples": ["Sales office mana dengan rata-rata picking terlama?"]},
    {"name": "Unloading", "metrics": ["average_unloading_minutes"], "examples": ["Sales office mana dengan rata-rata unloading terlama?"]},
    {"name": "SAT Promo", "metrics": ["promo_observation_count"], "examples": ["Berapa observasi promo aktif pada Desember 2024?"]},
)

_DIMENSION_METRIC_OVERRIDES = {
    ("gross_billing_value", "material"): "material_sell_in_value",
}


def _metric_covers_concept(metric: str, concept: str) -> bool:
    checks = {
        "sell_in": "sell_in" in metric,
        "sell_out": "sell_out" in metric,
        "stock_tempo": "stock_tempo" in metric or "warehouse_stock" in metric,
        "dc_stock": "dc_stock" in metric,
        "store_stock": "store_stock" in metric,
        "oos": "oos" in metric,
        "service_level": "fill_rate" in metric or metric.startswith("service_"),
    }
    return checks[concept]


class SemanticContextService:
    def __init__(self, project_dir: Path = PROJECT_DIR) -> None:
        self.registry = TempoOssieRegistry(project_dir)
        self.datasets = self.registry.datasets
        self.metrics = self.registry.metrics
        self._tables: dict[str, TablePolicy] = {}
        for dataset_name, dataset in self.datasets.items():
            fields = self.registry.dataset_fields[dataset_name]
            time_columns = {
                name for name, field in fields.items()
                if bool((field.get("dimension") or {}).get("is_time"))
                or name in {"calmonth", "calmonth_date", "reporting_month", "reporting_period", "thn", "bln"}
            }
            self._tables[str(dataset["source"]).casefold()] = TablePolicy(
                name=str(dataset["source"]).casefold(),
                domain=dataset_name,
                columns=frozenset(name.casefold() for name in fields),
                time_columns=frozenset(time_columns),
                description=str(dataset.get("description") or ""),
            )
        self._curated = {
            " ".join(item.question.casefold().split()): CURATED_CONTRACTS[item.id]
            for item in QuestionBank().all()
        }

    @property
    def table_names(self) -> frozenset[str]:
        return frozenset(self._tables)

    def table_policy(self, name: str) -> TablePolicy:
        try:
            return self._tables[name.casefold()]
        except KeyError as exc:
            raise ValueError(f"Table not allowed: {name.casefold()}") from exc

    def resolve(self, question: str) -> dict[str, Any]:
        contract = self._curated.get(" ".join(question.casefold().split()))
        if contract:
            if contract.get("strategy") == "sql_fallback":
                return {"status": "fallback", "reason": "curated_multi_metric", **contract}
            metric = str(contract["metric"])
            return {
                "status": "resolved",
                "metric": metric,
                "matched_alias": "curated_contract",
                "definition": self.metric_definition(metric),
                "dimensions": list(contract.get("dimensions", [])),
                "dimension_mismatch": [],
            }
        resolution = self.registry.resolve_metric(question)
        if resolution.get("status") == "resolved":
            mismatch = list(resolution.get("dimension_mismatch") or [])
            if len(mismatch) == 1:
                replacement = _DIMENSION_METRIC_OVERRIDES.get((str(resolution["metric"]), mismatch[0]))
                if replacement:
                    return {
                        "status": "resolved",
                        "metric": replacement,
                        "matched_alias": resolution.get("matched_alias"),
                        "resolved_by": "governed_dimension_override",
                        "definition": self.metric_definition(replacement),
                        "dimensions": mismatch,
                        "dimension_mismatch": [],
                    }
            normalized = question.casefold().replace("–", "-")
            concepts = {
                concept
                for concept, patterns in _CONCEPT_PATTERNS.items()
                if any(pattern in normalized for pattern in patterns)
            }
            metric = str(resolution["metric"])
            missing = sorted(concept for concept in concepts if not _metric_covers_concept(metric, concept))
            if len(concepts) >= 2 and missing:
                return {
                    "status": "fallback",
                    "reason": "multi_concept_metric_mismatch",
                    "requested_concepts": sorted(concepts),
                    "missing_concepts": missing,
                    "candidate_metric": metric,
                }
        return resolution

    def metric_definition(self, metric: str) -> dict[str, Any]:
        return self.registry.metric_definition(metric)

    def compile_governed(self, metric: str, question: str, requested_dimensions: list[str] | None = None) -> str:
        definition = self.metric_definition(metric)
        dataset_name = definition["base_dataset"]
        dataset = self.datasets[dataset_name]
        allowed = set(definition["allowed_dimensions"])
        lowered = question.casefold()
        hints = {
            "material_code": ("material code", "kode material"),
            "material": ("material", "produk", "sku"),
            "cust_id": ("customer", "pelanggan", "store"),
            "cust_code": ("customer code", "kode customer"),
            "customer": ("customer", "pelanggan"),
            "sales_office": ("sales office", "kantor penjualan"),
            "sales_off": ("sales off",),
            "branch": ("branch", "cabang"),
            "e_store": ("e-store", "estore"),
            "plu": ("plu",),
            "plant": ("plant",),
            "division": ("division", "divisi"),
        }
        dimensions = list(requested_dimensions) if requested_dimensions is not None else [name for name, terms in hints.items() if name in allowed and any(term in lowered for term in terms)]
        if any(name not in allowed for name in dimensions):
            raise ValueError("Requested dimension is not governed for this metric")
        if requested_dimensions is None and "dcname" in allowed and re.search(r"(?:per|by)\s+dc\b|\bdc\s+mana\b|\bnama dc\b", lowered):
            dimensions.append("dcname")
        if requested_dimensions is None and any(term in lowered for term in ("bulan", "bulanan", "month", "trend", "tren")):
            if {"thn", "bln"} <= allowed:
                dimensions = ["thn", "bln", *dimensions]
            else:
                for time_dimension in ("calmonth", "calmonth_date", "reporting_month", "reporting_period", "bln"):
                    if time_dimension in allowed:
                        dimensions.insert(0, time_dimension)
                        break
        dimensions = list(dict.fromkeys(dimensions))
        expression = definition["expression"].replace(f"{dataset_name}.", "d.")
        projections = [f"d.{name} AS {name}" for name in dimensions]
        projections.append(f"{expression} AS metric_value")
        predicates = []
        for field in definition.get("required_filters", []):
            predicates.append(f"d.{field} = TRUE")
        if definition.get("row_filter"):
            predicates.append(f"({definition['row_filter']})")
        fields = self.registry.dataset_fields[dataset_name]
        if "calmonth" in fields:
            predicates.append("d.calmonth BETWEEN 202410 AND 202412")
        sql = ["SELECT", "  " + ",\n  ".join(projections), f"FROM {dataset['source']} d"]
        if predicates:
            sql.append("WHERE " + "\n  AND ".join(predicates))
        if dimensions:
            sql.append("GROUP BY " + ", ".join(f"d.{name}" for name in dimensions))
        ascending = any(term in lowered for term in ("terendah", "terkecil", "lowest", "bottom"))
        sql.append(f"ORDER BY metric_value {'ASC' if ascending else 'DESC'}")
        top = re.search(r"(?:top|teratas)\s+(\d+)", lowered)
        limit = min(int(top.group(1)), 200) if top else 50
        sql.append(f"LIMIT {limit}")
        return "\n".join(sql)

    def planner_context(self, domains: list[str] | None = None) -> dict[str, Any]:
        selected: set[str] = set()
        for domain in domains or []:
            if domain in self.datasets:
                selected.add(domain)
            else:
                selected.update(_DOMAIN_DATASETS.get(domain, set()))
        if not selected:
            selected = set(self.datasets)
        datasets = []
        for name in sorted(selected):
            dataset = self.datasets[name]
            policy = self.table_policy(dataset["source"])
            datasets.append({
                "name": name,
                "view": policy.name,
                "description": policy.description,
                "columns": sorted(policy.columns),
                "time_columns": sorted(policy.time_columns),
            })
        metrics = []
        for name in sorted(self.metrics):
            definition = self.metric_definition(name)
            if definition["base_dataset"] in selected:
                metrics.append({
                    "name": name,
                    "description": definition["description"],
                    "dataset": definition["base_dataset"],
                    "dimensions": definition["allowed_dimensions"],
                })
        return {
            "authority": "Apache Ossie TEMPO Q4 2024",
            "datasets": datasets,
            "metrics": metrics,
            "relationships": [],
            "join_policy": "No runtime joins; use only published cross-domain views.",
        }

    def greeting_context(self) -> dict[str, Any]:
        summary = self.registry.capability_summary()
        return {
            "scope": summary.get("scope") or "TEMPO Q4 2024",
            "domains": [
                "Sales / Sell-In", "B2B / Sell-Out", "Stock Tempo",
                "Stock SAT-IDM", "SAT OOS", "Service Level",
                "Picking", "Unloading", "SAT Promo",
            ],
            "examples": list(summary.get("examples") or [])[:4],
            "domain_options": list(_GUIDANCE_DOMAIN_OPTIONS),
            "dataset_count": len(self.datasets),
            "metric_count": len(self.metrics),
        }

    def guidance_context(self, question: str) -> dict[str, Any]:
        normalized = question.casefold().replace("–", "-")
        mentioned_topic = next(
            (
                name for name, terms in {
                    "stock": ("stok", "stock", "inventory"),
                    "sales": ("sales", "penjualan", "sell-in", "sell out", "sell-out"),
                    "oos": ("oos", "out of stock"),
                    "b2b": ("b2b",),
                }.items()
                if any(term in normalized for term in terms)
            ),
            None,
        )
        excluded_topic = mentioned_topic if "selain" in normalized else None
        topic = None if excluded_topic else mentioned_topic
        context = self.greeting_context()
        if not topic:
            return {**context, "focus": None, "excluded_focus": excluded_topic, "metrics": []}

        selected_datasets: set[str] = set()
        for domain in _GUIDANCE_TOPICS[topic]:
            selected_datasets.update(_DOMAIN_DATASETS[domain])
        metrics = [
            {
                "name": name,
                "description": definition["description"],
                "dimensions": definition["allowed_dimensions"],
            }
            for name in sorted(self.metrics)
            if (definition := self.metric_definition(name))["base_dataset"] in selected_datasets
        ]
        metric_names = {item["name"] for item in metrics}
        examples = [
            str(item["question"])
            for item in self.registry.golden_questions.get("questions", [])
            if item.get("metric") in metric_names
            and item.get("expected_status") in {"supported", "supported_with_caveat"}
        ][:6]
        return {**context, "focus": topic, "excluded_focus": None, "metrics": metrics, "examples": examples}


@lru_cache(maxsize=1)
def get_semantic_context() -> SemanticContextService:
    return SemanticContextService()
