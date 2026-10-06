from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
import re

from app.core.config import get_settings
from app.semantic.domain_graph import (
    build_business_context,
    classify_cabang_grain,
    try_clarification_intent,
    try_governed_intent_route,
)
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


_SAP_MATERIAL_RE = re.compile(r"\b(\d{3}-\d{2}-\d{2})\b")
_FE_MATERIAL_RE = re.compile(r"\b(FE[0-9A-Z]+)\b", re.IGNORECASE)
_BRANCH_SKIP = frozenset({"partner", "alfamart", "tempo", "b2b", "dc", "branch", "cabang", "outlet", "store"})
_PLU_ENTITY_RE = re.compile(r"\bplu\s+['\"]?(\d+)\b", re.IGNORECASE)
_POLITE_SEKARANG_PREFIX_RE = re.compile(
    r"^(?:\s*)sekarang\s+(?:bisa|boleh|tolong|mohon|please|can|could)\b",
    re.IGNORECASE,
)
_RANKING_TERMS = (
    "tertinggi", "terbesar", "paling tinggi", "paling besar", "paling banyak",
    "terendah", "terkecil", "paling kecil", "paling rendah", "paling sedikit",
    "terburuk", "terjelek", "paling jelek", "ranking", "peringkat", "urutkan",
)
_VOLUME_CLASSIFICATION_TERMS = (
    "high-runner", "high runner", "highrunner",
    "long tail", "long-tail", "longtail",
    "fast moving", "fast-moving", "slow moving", "slow-moving",
    "volume", "laris", "terlaris", "movement", "runner",
)


def _question_wants_sell_in_volume_context(question: str) -> bool:
    lowered = question.casefold()
    return any(term in lowered for term in _VOLUME_CLASSIFICATION_TERMS)


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sanitize_office_dimension_hints(question: str, dimensions: list[str], allowed: set[str]) -> list[str]:
    """Avoid sales_off substring false match inside 'sales office'; map cabang ops to sales_office."""
    lowered = question.casefold()
    folded = re.sub(r"[\s_\-]+", "", lowered)
    out = list(dimensions)
    metric_uses_office = "sales_office" in allowed and "sales_off" not in allowed
    if metric_uses_office or "sales_office" in allowed:
        if "salesoffice" in folded or "kantor penjualan" in lowered or re.search(
            r"\bsales\s+office\b", lowered
        ):
            out = [d for d in out if d != "sales_off"]
            if "sales_office" in allowed and "sales_office" not in out:
                out.append("sales_office")
    picking_unloading = any(term in lowered for term in ("picking", "unloading"))
    if picking_unloading and "sales_office" in allowed and not out:
        out.append("sales_office")
    return list(dict.fromkeys(out))


def _branch_name_predicate(branch_value: str) -> str:
    """Match DC labels when the user names a city fragment (e.g. cabang palembang → DC Palembang)."""
    cleaned = branch_value.strip()
    literal = _sql_string_literal(cleaned)
    if " " not in cleaned and not cleaned.upper().startswith("DC"):
        return f"UPPER(d.branch) LIKE CONCAT('%', UPPER({literal}), '%')"
    return f"d.branch = {literal}"


_BRANCH_PREP = frozenset({"di", "ke", "untuk", "pada", "dalam", "dan", "atau", "the", "a"})


def _normalize_branch_entity_candidate(candidate: str) -> str | None:
    """Turn 'cabang di Alfamart' / 'di palembang' into a branch filter token, or None if not a branch name."""
    cleaned = candidate.strip().strip("?.,!;:\"'""''")
    if cleaned.casefold() in _BRANCH_PREP:
        return None
    cleaned = re.sub(r"^(?:di|ke|untuk|pada|dalam)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+q[1-4]\s+\d{4}\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    if not cleaned or cleaned.casefold() in _BRANCH_PREP:
        return None
    if cleaned.casefold() in _BRANCH_SKIP:
        return None
    head = cleaned.split()[0].casefold() if cleaned.split() else ""
    if head in {"alfamart", "partner", "idm", "sat", "b2b"}:
        return None
    # Partner network context, not a DC label (e.g. "penjualan cabang di Alfamart" = rank all DCs).
    if cleaned.casefold() in {"alfamart", "partner", "idm", "sat", "sat-idm", "sat idm", "b2b", "sell-out", "sellout"}:
        return None
    rank_tail = {
        "tertinggi", "terendah", "terbesar", "terkecil", "terbanyak", "terburuk", "terlaris",
        "terbaik", "standard", "industri", "industry", "ranking", "teratas", "terbawah",
    }
    parts = cleaned.split()
    while len(parts) > 1 and parts[-1].casefold() in rank_tail:
        parts.pop()
    cleaned = " ".join(parts).strip()
    if not cleaned or cleaned.casefold() in _BRANCH_SKIP:
        return None
    if cleaned.casefold() in {"alfamart", "partner", "idm", "sat", "sat-idm", "sat idm"}:
        return None
    return cleaned


def _asks_data_snapshot(question: str) -> bool:
    lowered = question.casefold()
    if any(term in lowered for term in ("saat ini", "bulan ini", "terkini", "latest", "current")):
        return True
    if "sekarang" not in lowered:
        return False
    if _POLITE_SEKARANG_PREFIX_RE.search(lowered):
        return False
    if re.search(r"\bsekarang\s+(?:bisa|bantu|tampilkan|keluarkan|tolong)\b", lowered):
        return False
    if re.search(r"\b(?:stok|stock|penjualan|sales|fill\s+rate|data|nilai)\s+sekarang\b", lowered):
        return True
    if re.search(r"\bsekarang\s+berapa\b", lowered):
        return True
    return False


def _question_requests_ranking(question: str) -> tuple[bool, re.Match[str] | None]:
    lowered = question.casefold()
    top = re.search(r"(?:top|teratas)\s+(\d+)", lowered)
    if not top:
        top = re.search(r"\b(\d+)\s+(?:branch|branches|cabang)\b", lowered)
    requests_ranking = bool(top) or any(term in lowered for term in _RANKING_TERMS)
    if not requests_ranking and re.search(
        r"\btop\s+(?:penjualan|sales|produk|sku|material|dc|cabang|branch|outlet|toko|gerai)\b",
        lowered,
    ):
        requests_ranking = True
    return requests_ranking, top


def _extract_entity_predicates(question: str, fields: set[str]) -> list[str]:
    predicates: list[str] = []
    lowered = question.casefold()

    for match in _SAP_MATERIAL_RE.finditer(question):
        code = match.group(1)
        if "material" in fields:
            predicates.append(f"d.material = {_sql_string_literal(code)}")
            break
        if "material_code" in fields:
            predicates.append(f"d.material_code = {_sql_string_literal(code)}")
            break

    if not any("material" in item or "material_code" in item for item in predicates):
        fe_match = _FE_MATERIAL_RE.search(question)
        if fe_match and "material" in fields:
            predicates.append(f"d.material = {_sql_string_literal(fe_match.group(1).upper())}")

    branch_code: str | None = None
    for pattern in (
        r"\b(?:di\s+)?cabang\s+([^,]+?)(?:\s*,|\s+top\b|\s+based\b|\s+produk\b|\s+product\b|$)",
        r"\bbranch\s+([^,]+?)(?:\s*,|\s+top\b|\s+based\b|\s+produk\b|\s+product\b|$)",
        r"\b(?:di\s+)?cabang\s+(?!di\b|ke\b|untuk\b|pada\b)['\"]?([0-9A-Za-z_-]+)",
        r"\bbranch\s+(?!di\b|ke\b|untuk\b|pada\b)['\"]?([0-9A-Za-z_-]+)",
        r"\boutlet\s+['\"]?([0-9A-Za-z_-]+)",
        r"\be[\s-]?store\s+['\"]?([0-9A-Za-z_-]+)",
    ):
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match:
            candidate = _normalize_branch_entity_candidate(match.group(1))
            if candidate:
                branch_code = candidate
                break
    if branch_code:
        if "branch" in fields:
            predicates.append(_branch_name_predicate(branch_code))
        elif "e_store" in fields:
            predicates.append(f"d.e_store = {_sql_string_literal(branch_code)}")

    plu_match = _PLU_ENTITY_RE.search(lowered)
    if plu_match:
        code = plu_match.group(1)
        if "plu" in fields:
            predicates.append(f"d.plu = {_sql_string_literal(code)}")
        elif "kode_plu" in fields:
            predicates.append(f"d.kode_plu = {_sql_string_literal(code)}")

    if "dcname" in fields and not any("dcname" in item for item in predicates):
        dc_match = re.search(r"\bdc\s+([a-zA-Z]+)", question, re.IGNORECASE)
        if dc_match:
            city = dc_match.group(1)
            predicates.append(
                f"UPPER(d.dcname) LIKE CONCAT('%', UPPER({_sql_string_literal(city)}), '%')"
            )

    return predicates


def _filtered_columns(predicates: list[str]) -> list[str]:
    columns: list[str] = []
    for predicate in predicates:
        column = predicate.split("=", 1)[0].strip().removeprefix("d.").strip()
        if column and column not in columns:
            columns.append(column)
    return columns


def is_governed_entity_lookup(question: str, fields: set[str]) -> bool:
    if not _extract_entity_predicates(question, fields):
        return False
    requests_ranking, top = _question_requests_ranking(question)
    return not requests_ranking and top is None


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

_METRIC_HELP_ID: dict[str, str] = {
    "gross_billing_value": "Gross Sales / Sell-In",
    "b2b_branch_sell_out_value": "nilai Sell-Out B2B per cabang",
    "stock_tempo_total_qty": "stok gudang Tempo",
    "sat_dc_stock_quantity": "stok DC partner (Alfamart)",
    "sat_store_stock_quantity": "stok toko retail",
    "sat_oos_rate": "tingkat OOS di toko SAT",
    "service_fill_rate": "service level / fill rate cabang",
    "average_picking_minutes": "durasi picking gudang",
    "average_unloading_minutes": "durasi unloading gudang",
    "promo_observation_count": "observasi promo aktif",
}

_DOMAIN_NAMES_BY_GUIDANCE_FOCUS: dict[str, frozenset[str]] = {
    "sales": frozenset({"Sales / Sell-In"}),
    "stock": frozenset({"Stock Tempo", "Stock SAT (Alfamart)"}),
    "oos": frozenset({"SAT OOS"}),
    "b2b": frozenset({"B2B / Sell-Out"}),
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

_DIMENSION_METRIC_OVERRIDES: dict[tuple[str, str], str | tuple[str, list[str]]] = {
    ("gross_billing_value", "material"): "material_sell_in_value",
    ("gross_billing_value", "branch"): ("sales_office_sell_in_value", ["sales_office"]),
    ("gross_billing_value", "sales_office"): ("sales_office_sell_in_value", ["sales_office"]),
    ("gross_billing_value", "sales_off"): ("sales_office_sell_in_value", ["sales_office"]),
}


def _normalize_sales_typos(question: str) -> str:
    """Lightweight typo fixes so governed routing still recognizes sales intent."""
    lowered = question.casefold().replace("–", "-")
    return re.sub(r"\bpenjualn\b", "penjualan", lowered)


def _question_prefers_sell_out(question: str) -> bool:
    lowered = _normalize_sales_typos(question)
    sell_in = any(
        term in lowered
        for term in ("sell-in", "sell in", "klarifikasi pengguna: sell-in", "tempo ke customer", "general trade")
    )
    sell_out = any(
        term in lowered
        for term in ("sell-out", "sell out", "partner ke konsumen", "penjualan partner")
    )
    return sell_out and not sell_in


def _question_requests_branch_sales_ranking(question: str) -> bool:
    lowered = _normalize_sales_typos(question)
    branch = bool(re.search(r"\b(branch|cabang|branches|sales\s+office)\b", lowered))
    if not branch:
        return False
    sales = any(
        term in lowered
        for term in ("penjualan", "sales", "revenue", "billing", "omset", "omzet", "hitung", "tertinggi", "terbesar")
    )
    if not sales:
        requests_ranking, _ = _question_requests_ranking(question)
        if requests_ranking and "alfamart" in lowered:
            return True
        return False
    if _question_prefers_sell_out(question):
        return True
    return any(
        term in lowered
        for term in ("sell-in", "sell in", "klarifikasi pengguna: sell-in", "tempo ke customer")
    ) or not any(term in lowered for term in ("sell-out", "sell out"))


def _branch_ranking_metric(question: str, session_last_metric: str | None = None) -> tuple[str, list[str]]:
    if get_settings().business_graph_enabled:
        grain = classify_cabang_grain(question, session_last_metric=session_last_metric)
        if grain == "branch":
            return "b2b_branch_sell_out_value", ["branch"]
        if grain == "sales_office":
            return "sales_office_sell_in_value", ["sales_office"]
    if _question_prefers_sell_out(question):
        return "b2b_branch_sell_out_value", ["branch"]
    return "sales_office_sell_in_value", ["sales_office"]


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

    def _try_session_metric_continuation(
        self,
        question: str,
        analysis_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        metric = analysis_context.get("last_metric")
        if not isinstance(metric, str) or not metric.strip():
            return None
        normalized = " ".join(question.casefold().replace("–", "-").split())
        if not any(
            term in normalized
            for term in (
                "tadi",
                "pertanyaan tadi",
                "sebelumnya",
                "lanjut",
                "tersebut",
                "breakdown",
                "per bulan",
                "bulanan",
                "oktober",
                "november",
                "desember",
                "total tadi",
                "teratas tadi",
                "paling kritis",
                "rank 1",
                "urutan 1",
                "dari hasil",
                "dari ranking",
                "dari daftar",
            )
        ):
            return None
        definition = self.metric_definition(metric)
        allowed = set(definition.get("allowed_dimensions") or [])
        dimensions = [str(d) for d in (analysis_context.get("last_dimensions") or []) if d in allowed]
        if any(
            term in normalized
            for term in ("bulan", "bulanan", "oktober", "november", "desember", "month")
        ):
            for time_dim in ("calmonth", "reporting_period", "calmonth_date", "bln"):
                if time_dim in allowed:
                    dimensions = [time_dim, *[d for d in dimensions if d != time_dim]]
                    break
        if not dimensions and allowed:
            dimensions = [sorted(allowed)[0]]
        return {
            "status": "resolved",
            "metric": metric,
            "matched_alias": "session_metric_continuation",
            "dimensions": dimensions,
            "dimension_mismatch": [],
        }

    def resolve(
        self,
        question: str,
        session_last_metric: str | None = None,
        session_analysis_context: dict[str, Any] | None = None,
        turn_understanding: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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

        def resolved(metric: str, dimensions: list[str], *, matched_alias: str = "governed_intent_route") -> dict[str, Any]:
            return {
                "status": "resolved",
                "metric": metric,
                "matched_alias": matched_alias,
                "definition": self.metric_definition(metric),
                "dimensions": dimensions,
                "dimension_mismatch": [],
            }

        if get_settings().business_graph_enabled:
            clarify = try_clarification_intent(question)
            if clarify:
                return clarify

        if session_analysis_context:
            from app.services.conversational import TurnUnderstanding
            from app.services.follow_up import try_follow_up_governed_resolution

            understanding = None
            if isinstance(turn_understanding, dict):
                try:
                    understanding = TurnUnderstanding.model_validate(turn_understanding)
                except Exception:
                    understanding = None
            follow = try_follow_up_governed_resolution(
                question, session_analysis_context, understanding
            )
            if not follow:
                follow = self._try_session_metric_continuation(question, session_analysis_context)
            if follow and follow.get("status") == "resolved":
                metric = str(follow["metric"])
                follow["definition"] = self.metric_definition(metric)
                return follow

        if get_settings().business_graph_enabled:
            graph_intent = try_governed_intent_route(question, session_last_metric=session_last_metric)
            if graph_intent:
                return resolved(
                    str(graph_intent["metric"]),
                    list(graph_intent.get("dimensions") or []),
                    matched_alias=str(graph_intent.get("matched_alias") or "domain_graph_intent"),
                )

        if re.search(r"\bFE\d+\b", question, flags=re.IGNORECASE) and any(
            term in lowered for term in ("sell-in", "sell in", "sellin")
        ) and any(term in lowered for term in ("per bulan", "bulanan", "tren", "trend", "cukup tampilkan", "cukup")):
            return resolved(
                "material_sell_in_value",
                ["calmonth", "material"],
                matched_alias="cross_fe001_sell_in_trend",
            )

        if re.search(r"\bFE\d+\b", question, flags=re.IGNORECASE) and any(
            term in lowered for term in ("stok tempo", "stock tempo", "hubungan stok", "stok gudang tempo")
        ) and any(term in lowered for term in ("sell-in", "sell in", "sellin")):
            return resolved(
                "stock_tempo_to_sell_in_ratio",
                ["calmonth", "material"],
                matched_alias="cross_stock_sell_in_material",
            )

        if any(term in lowered for term in ("quantity", "kuantitas", "qty", "unit")) and any(
            term in lowered for term in ("terjual", "sell-in", "sell in", "paling banyak", "terbanyak")
        ) and any(term in lowered for term in ("top", "produk", "material")):
            return resolved("material_sell_in_quantity", ["material"], matched_alias="material_sell_in_quantity_rank")

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
                # service_level_material carries sell-in alongside SL PO/DO
                # for high-runner vs long-tail follow-ups on the same query.
                return resolved("service_fill_rate", ["material"])
            if ("sales" in words and "office" in words) or bool(words & {"cabang", "branch"}):
                return resolved("sales_office_service_fill_rate", ["sales_off"])
            return resolved("company_fill_rate", [])
        if mentions_fill_rate_band and words & {"material", "jumlah", "berapa", "distribusi"}:
            return resolved("service_material_month_count", ["fill_rate_band"])
        if {"po", "do"} <= words and bool(words & {"gap", "selisih"}):
            wants_office_rank = (
                ("sales" in words and "office" in words)
                or "office" in words
                or bool(words & {"cabang", "branch", "mana"})
            )
            if wants_office_rank:
                return resolved("sales_office_service_unfulfilled_quantity", ["sales_off"])
            return resolved("service_unfulfilled_quantity", [])

        office_codes = re.findall(r"\b(0\d{3})\b", question)
        if len(office_codes) >= 2 and any(
            term in lowered for term in ("bandingkan", "banding", "perbedaan", "membedakan", "compare", " vs ")
        ):
            if _question_prefers_sell_out(question):
                return resolved("b2b_branch_sell_out_value", ["branch", "material"])
            wants_material = any(term in lowered for term in ("material", "produk", "sku"))
            wants_office_total = any(term in lowered for term in ("total", "office", "sales office", "kantor"))
            if wants_office_total and not wants_material:
                return resolved("sales_office_sell_in_value", ["sales_office"])
            return resolved("sales_office_material_sell_in_value", ["sales_office", "material"])

        if _question_requests_branch_sales_ranking(question):
            metric, dimensions = _branch_ranking_metric(question, session_last_metric)
            return resolved(metric, dimensions)

        resolution = self.registry.resolve_metric(question)
        if resolution.get("status") == "resolved":
            mismatch = list(resolution.get("dimension_mismatch") or [])
            if len(mismatch) == 1:
                replacement = _DIMENSION_METRIC_OVERRIDES.get((str(resolution["metric"]), mismatch[0]))
                if replacement:
                    if isinstance(replacement, tuple):
                        metric_name, dimensions = replacement
                    else:
                        metric_name, dimensions = replacement, mismatch
                    return {
                        "status": "resolved",
                        "metric": metric_name,
                        "matched_alias": resolution.get("matched_alias"),
                        "resolved_by": "governed_dimension_override",
                        "definition": self.metric_definition(metric_name),
                        "dimensions": dimensions,
                        "dimension_mismatch": [],
                    }
                branch_override = _branch_ranking_metric(question, session_last_metric)
                if mismatch[0] in ("branch", "sales_office", "sales_off") and str(resolution["metric"]) in {
                    "gross_billing_value",
                    "material_sell_in_value",
                    "billing_quantity",
                }:
                    metric_name, dimensions = branch_override
                    return {
                        "status": "resolved",
                        "metric": metric_name,
                        "matched_alias": resolution.get("matched_alias"),
                        "resolved_by": "governed_branch_sales_override",
                        "definition": self.metric_definition(metric_name),
                        "dimensions": dimensions,
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

    def compile_governed(
        self,
        metric: str,
        question: str,
        requested_dimensions: list[str] | None = None,
        extra_predicates: list[str] | None = None,
    ) -> str:
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
        dimensions = _sanitize_office_dimension_hints(question, dimensions, allowed)
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
        fields = self.registry.dataset_fields[dataset_name]
        field_set = set(fields)
        entity_predicates = _extract_entity_predicates(question, field_set)
        office_codes = sorted(set(re.findall(r"\b(0\d{3})\b", question)))
        if len(office_codes) >= 2:
            if "sales_office" in field_set:
                in_list = ", ".join(_sql_string_literal(code) for code in office_codes)
                entity_predicates.append(f"d.sales_office IN ({in_list})")
            elif "sales_off" in field_set:
                in_list = ", ".join(_sql_string_literal(code) for code in office_codes)
                entity_predicates.append(f"d.sales_off IN ({in_list})")
            elif "branch" in field_set:
                in_list = ", ".join(_sql_string_literal(code) for code in office_codes)
                entity_predicates.append(f"d.branch IN ({in_list})")
        for column in _filtered_columns(entity_predicates):
            if column in allowed and column not in dimensions:
                dimensions.append(column)
        entity_lookup = is_governed_entity_lookup(question, field_set)
        expression = definition["expression"].replace(f"{dataset_name}.", "d.")
        projections = [f"d.{name} AS {name}" for name in dimensions]
        projections.append(f"{expression} AS metric_value")
        if _question_wants_sell_in_volume_context(question):
            if "sell_in_bill_qty" in field_set:
                projections.append("SUM(d.sell_in_bill_qty) AS sell_in_qty")
            if "sell_in_bill_val" in field_set:
                projections.append("SUM(d.sell_in_bill_val) AS sell_in_val")
        predicates = []
        for field in definition.get("required_filters", []):
            predicates.append(f"d.{field} = TRUE")
        if definition.get("row_filter"):
            predicates.append(f"({definition['row_filter']})")
        predicates.extend(entity_predicates)
        if extra_predicates:
            for predicate in extra_predicates:
                stripped = predicate.strip()
                col_match = re.match(r"d\.(\w+)\s*(?:=|IN\b)", stripped, flags=re.IGNORECASE)
                if col_match and col_match.group(1) in field_set:
                    predicates.append(stripped)
                else:
                    column = stripped.split("=", 1)[0].strip().removeprefix("d.").strip()
                    if column in field_set:
                        predicates.append(stripped)
        asks_current_snapshot = _asks_data_snapshot(question)
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
        ascending = any(
            term in lowered
            for term in (
                "terendah", "terkecil", "paling kecil", "paling rendah",
                "paling sedikit", "paling jelek", "terjelek", "terburuk", "lowest", "bottom",
            )
        )
        duration_metric = "picking" in metric.casefold() or "unloading" in metric.casefold()
        if duration_metric:
            if any(
                term in lowered
                for term in (
                    "tercepat",
                    "paling cepat",
                    "paling efisien",
                    "efisien",
                    "fastest",
                    "most efficient",
                    "shortest",
                    "paling singkat",
                )
            ):
                ascending = True
            elif any(
                term in lowered
                for term in (
                    "terlama",
                    "terlambat",
                    "paling lambat",
                    "tertinggi",
                    "slowest",
                    "longest",
                )
            ):
                ascending = False
        if "oos" in metric.casefold() and any(
            term in lowered for term in ("terburuk", "terparah", "terjelek", "paling jelek", "worst")
        ):
            # Higher OOS rate is worse; do not ASC-sort "terburuk" to near-zero rates.
            ascending = False
        having_clauses: list[str] = []
        if "fill_rate" in metric and ascending and "service_po_qty" in field_set:
            having_clauses.append("SUM(d.service_po_qty) > 0")
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
            having_clauses.append(f"{expression} = 0")
        if having_clauses:
            sql.append("HAVING " + " AND ".join(having_clauses))
        requests_ranking, top = _question_requests_ranking(question)
        if trend_time_dimension_inserted and not requests_ranking and not entity_lookup:
            # A pure trend/"per bulan" question (no top-N or superlative
            # ranking intent) should read chronologically, not value-ranked
            # - otherwise "naik atau turun" is unanswerable from the result
            # order.
            order_column = "d.thn, d.bln" if {"thn", "bln"} <= allowed else f"d.{dimensions[0]}"
            sql.append(f"ORDER BY {order_column} ASC")
        elif entity_lookup:
            if dimensions:
                sql.append("ORDER BY " + ", ".join(f"d.{name} ASC" for name in dimensions))
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
        if entity_lookup:
            limit = 1
        elif top:
            limit = min(int(top.group(1)), maximum)
        else:
            limit = default
        if len(office_codes) >= 2 and "material" in dimensions:
            per_branch = 10
            per_branch_match = re.search(r"\b(\d+)\s+material", lowered)
            if per_branch_match:
                per_branch = min(int(per_branch_match.group(1)), 25)
            needed = per_branch * len(office_codes)
            limit = min(max(limit, needed), maximum)
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
        payload: dict[str, Any] = {
            "authority": "Apache Ossie TEMPO Q4 2024",
            "datasets": datasets,
            "metrics": metrics,
            "relationships": [],
            "join_policy": "No runtime joins; use only published cross-domain views.",
        }
        return payload

    def business_graph_snippet(
        self,
        question: str,
        *,
        session_last_metric: str | None = None,
    ) -> dict[str, Any] | None:
        if not get_settings().business_graph_enabled:
            return None
        return build_business_context(question, session_last_metric=session_last_metric)

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
            "domain_capability_lines": self.domain_capability_insight_lines(),
            "dataset_count": len(self.datasets),
            "metric_count": len(self.metrics),
        }

    def domain_capability_insight_lines(self, *, exclude_focus: str | None = None) -> list[str]:
        skip = _DOMAIN_NAMES_BY_GUIDANCE_FOCUS.get(exclude_focus or "", frozenset())
        lines: list[str] = []
        for option in _GUIDANCE_DOMAIN_OPTIONS:
            if option["name"] in skip:
                continue
            helps = ", ".join(
                _METRIC_HELP_ID.get(metric, metric.replace("_", " "))
                for metric in option["metrics"]
            )
            example = option["examples"][0] if option.get("examples") else ""
            lines.append(f"{option['name']}: {helps}. Contoh: {example}")
        return lines

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
