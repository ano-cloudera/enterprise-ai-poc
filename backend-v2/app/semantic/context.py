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
    "stock_sat_idm": {"sat_dc_month"},
    "sat_oos": {"sat_oos_material_month"},
    "cross_domain": {
        "material_360", "customer_reconciliation", "stock_tempo_sales_material_month",
        "sales_b2b_material_month", "b2b_sat_branch_month", "sat_dc_oos_material_month",
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
    "picking": ("picking",),
    "unloading": ("unloading",),
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
        "name": "Stock SAT (Alfamart)",
        "metrics": ["sat_dc_stock_quantity", "sat_store_stock_quantity"],
        "examples": ["Berapa stok DC Alfamart atau stok retail per division?"],
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
        "picking": "picking" in metric,
        "unloading": "unloading" in metric,
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

        lowered = question.casefold()
        words = set(re.findall(r"[a-z0-9]+", lowered))

        def resolved(metric: str, dimensions: list[str]) -> dict[str, Any]:
            return {
                "status": "resolved",
                "metric": metric,
                "matched_alias": "governed_intent_route",
                "definition": self.metric_definition(metric),
                "dimensions": dimensions,
                "dimension_mismatch": [],
            }

        # Shelf-survey OOS language contains generic words such as "stok",
        # "toko", and "kosong". Route this governed audit intent before the
        # broader warehouse/DC/store stock-scope ambiguity can capture it.
        mentions_oos = "oos" in words or "out of stock" in lowered or (
            "kosong" in words and bool(words & {"stok", "rak", "survei", "disurvei"})
        ) or (
            "kehabisan" in words and bool(words & {"stok", "stock"})
        )
        if mentions_oos and bool(words & {"sales", "penjualan"}) and bool(
            words & {"pengaruh", "dampak", "penurunan", "turun", "menurunkan"}
        ):
            return {
                "status": "unsupported",
                "reason": "oos_sales_causality_unavailable",
                "question": (
                    "Data SAT OOS dapat menunjukkan tingkat stok kosong, tetapi "
                    "belum mendukung klaim pengaruh atau besarnya penurunan sales."
                ),
            }
        if mentions_oos and any(
            phrase in lowered
            for phrase in ("store stock", "stok store", "stok toko", "dc stock", "stok dc", "stok tempo")
        ):
            return {
                "status": "fallback",
                "reason": "multi_concept_metric_mismatch",
                "requested_concepts": ["oos", "stock"],
                "missing_concepts": ["published_cross_domain_metric"],
            }
        if mentions_oos:
            dimensions: list[str] = []
            # "toko"/"outlet"/"gerai" alone is ambiguous between an
            # aggregate ("berapa persen toko yang kosong stoknya") and a
            # per-store ranking ("toko mana yang paling sering OOS") - only
            # the latter, signalled by "mana", should force a breakdown.
            wants_store_breakdown = bool(words & {"customer", "pelanggan"}) or (
                bool(words & {"toko", "outlet", "gerai"})
                and bool(words & {"mana", "tertinggi", "terbesar", "terendah", "terkecil", "terparah", "terburuk"})
            )
            if words & {"material", "produk", "sku"}:
                dimensions = ["material_code"]
            elif wants_store_breakdown:
                dimensions = ["cust_id", "cust_code"]
            return resolved("sat_oos_rate", dimensions)

        # "stok ... cover/bertahan ... (berapa) hari/bulan" is a stock-cover
        # question, even though it often also contains "penjualan" (e.g.
        # "hitung bisa meng-cover penjualan berapa hari dari stok tersebut")
        # - that "penjualan" is describing what the stock covers, not asking
        # for a separate Sell-In/Sell-Out figure. Route this before the
        # generic sales_stage ambiguity (registry.resolve_ambiguity, called
        # from resolve_metric below) can intercept it on the word
        # "penjualan" and ask an irrelevant Sell-In-vs-Sell-Out question.
        mentions_stock_cover = bool(words & {"stok", "stock"}) and (
            "cover" in lowered or bool(words & {"bertahan", "tahan"})
        )
        if mentions_stock_cover:
            result = resolved("months_of_stock_cover", ["material"] if "material" in words or words & {"produk", "sku"} else [])
            # months_of_stock_cover is company/material-grain only (no
            # branch/sales_off dimension exists for it) - if the question
            # also asks for a branch/cabang breakdown ("di cabang A"), that
            # part of the request cannot be honored. Surface it as a
            # dimension_mismatch (same signal used elsewhere) instead of
            # silently dropping it, so the analyst prompt can disclose the
            # gap rather than answer as if "cabang A" was never asked.
            if bool(words & {"cabang", "branch", "dc"}):
                result["dimension_mismatch"] = ["branch"]
            return result

        # These high-frequency Service Level intents have exact published
        # metrics. Resolve their requested grain deterministically instead of
        # leaving synonymous fill-rate metrics to alias-score tie breaking.
        mentions_fill_rate_band = "band" in words or "kategori" in lowered
        mentions_fill_or_service_level = ("fill" in words and "rate" in words) or (
            "service" in words and "level" in words
        )
        if mentions_fill_or_service_level:
            if mentions_fill_rate_band:
                return resolved("service_fill_rate", ["fill_rate_band"])
            if "material" in words:
                return resolved("material_fill_rate", ["material"])
            if ("sales" in words and "office" in words) or bool(words & {"cabang", "branch"}):
                return resolved("sales_office_service_fill_rate", ["sales_off"])
            return resolved("company_fill_rate", [])
        if mentions_fill_rate_band and words & {"material", "jumlah", "berapa", "distribusi"}:
            return resolved("service_material_month_count", ["fill_rate_band"])
        if {"po", "do"} <= words and bool(words & {"gap", "selisih"}):
            return resolved("service_unfulfilled_quantity", [])

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
            "branch": ("branch", "cabang", "dc"),
            "e_store": ("e-store", "estore", "outlet", "gerai", "per toko", "toko"),
            "plu": ("plu",),
            "plant": ("plant", "gudang"),
            "division": ("division", "divisi", "unit bisnis"),
            "fill_rate_band": ("band", "kategori fill rate", "fill rate band"),
            "mekanisme": ("mekanisme", "mechanism", "jenis promo", "tipe promo"),
            "program_status": ("program status", "status program", "kode status", "status kode"),
        }
        dimensions = list(requested_dimensions) if requested_dimensions is not None else [name for name, terms in hints.items() if name in allowed and any(term in lowered for term in terms)]
        if any(name not in allowed for name in dimensions):
            raise ValueError("Requested dimension is not governed for this metric")
        if requested_dimensions is None and "dcname" in allowed and re.search(r"(?:per|by)\s+dc\b|\bdc\s+mana\b|\bnama dc\b", lowered):
            dimensions.append("dcname")
        if requested_dimensions is None and dataset_name == "sat_promo_material_uplift" and "material" not in dimensions:
            # This dataset's only governed dimension is material, and it is
            # purpose-built for a "which material performed best" ranking
            # (the promo ROI/uplift proxy) - a company-wide SUM has no
            # meaningful business use here, so always break down by material
            # rather than requiring the question to say "per material".
            dimensions.append("material")
        trend_time_dimension_inserted = False
        # An empty requested_dimensions ([]) is what the governed_intent_route
        # shortcuts in resolve() pass for their default company-wide grain
        # (e.g. resolved("company_fill_rate", [])) - it is not the user
        # explicitly asking to omit all dimensions, so trend/"per bulan"
        # detection should still apply the same as the None (no-override)
        # case. A genuinely explicit non-empty list (e.g. ["material"]) is
        # never touched here.
        if (requested_dimensions is None or requested_dimensions == []) and any(
            term in lowered for term in ("bulan", "bulanan", "month", "trend", "tren")
        ):
            if {"thn", "bln"} <= allowed:
                dimensions = ["thn", "bln", *dimensions]
                trend_time_dimension_inserted = True
            else:
                for time_dimension in ("calmonth", "calmonth_date", "reporting_month", "reporting_period", "bln"):
                    if time_dimension in allowed:
                        dimensions.insert(0, time_dimension)
                        trend_time_dimension_inserted = True
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
        asks_current_snapshot = any(
            term in lowered for term in ("sekarang", "saat ini", "bulan ini", "terkini", "latest", "current")
        )
        asks_latest_available_month = asks_current_snapshot or "bulan lalu" in lowered or "last month" in lowered
        if "calmonth" in fields:
            predicates.append(
                "d.calmonth = 202412"
                if asks_current_snapshot
                else "d.calmonth BETWEEN 202410 AND 202412"
            )
        if {"thn", "bln"} <= set(fields) and asks_current_snapshot:
            predicates.extend(("d.thn = 2024", "d.bln = 'DEC'"))
        if "calmonth_date" in fields and asks_latest_available_month:
            predicates.append("d.calmonth_date = CAST('2024-12-01' AS DATE)")
        sql = ["SELECT", "  " + ",\n  ".join(projections), f"FROM {dataset['source']} d"]
        if predicates:
            sql.append("WHERE " + "\n  AND ".join(predicates))
        if dimensions:
            sql.append("GROUP BY " + ", ".join(f"d.{name}" for name in dimensions))
        requests_zero_movement = requested_dimensions is None and any(
            term in lowered
            for term in (
                "tidak laku", "zero movement", "tidak terjual",
                "tidak ada penjualan", "sama sekali tidak laku", "belum pernah terjual",
            )
        )
        if requests_zero_movement and dimensions:
            # Impala cannot resolve a SELECT alias (metric_value) inside
            # HAVING - repeat the actual aggregate expression instead.
            sql.append(f"HAVING {expression} = 0")
        ascending = any(
            term in lowered
            for term in (
                "terendah", "terkecil", "paling kecil", "paling rendah",
                "paling sedikit", "paling jelek", "terjelek", "terburuk", "lowest", "bottom",
            )
        )
        top = re.search(r"(?:top|teratas)\s+(\d+)", lowered)
        requests_ranking = bool(top) or any(
            term in lowered
            for term in (
                "tertinggi", "terbesar", "paling tinggi", "paling besar", "paling banyak",
                "terendah", "terkecil", "paling kecil", "paling rendah", "paling sedikit",
                "terburuk", "terjelek", "paling jelek", "ranking", "peringkat", "urutkan",
            )
        )
        if trend_time_dimension_inserted and not requests_ranking:
            # A pure trend/"per bulan" question (no top-N or superlative
            # ranking intent) should read chronologically, not value-ranked
            # - otherwise "naik atau turun" is unanswerable from the result
            # order.
            order_column = "d.thn, d.bln" if {"thn", "bln"} <= allowed else f"d.{dimensions[0]}"
            sql.append(f"ORDER BY {order_column} ASC")
        else:
            sql.append(f"ORDER BY metric_value {'ASC' if ascending else 'DESC'}")
        is_stock_metric = any(
            marker in metric
            for marker in ("stock", "warehouse_stock", "sat_dc", "sat_store")
        )
        is_promo_uplift_proxy = dataset_name == "sat_promo_material_uplift"
        if is_stock_metric or is_promo_uplift_proxy:
            maximum = 10
        else:
            maximum = 200
        default = 10 if dimensions else 50
        limit = min(int(top.group(1)), maximum) if top else default
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
                "Stock SAT (Alfamart)", "SAT OOS", "Service Level",
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
