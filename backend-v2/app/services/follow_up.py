"""Cross-domain analytic follow-ups: analysis context, entity binding, drill plans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.semantic.domain_graph import classify_cabang_grain
from app.services.session_context import (
    _last_governed_chart_turn,
    _last_governed_success_turn,
    _ranked_entities_from_rows,
    _rows_for_chart_follow_up,
    infer_governed_metric_from_turn,
)

from app.services.conversational import TurnUnderstanding

_TOP_N_RE = re.compile(r"\btop\s*(\d+)\b", re.IGNORECASE)
_RANK_N_RE = re.compile(r"\b(?:rank|urutan|no\.?)\s*(\d+)\b", re.IGNORECASE)
_MATERIAL_CODE_RE = re.compile(r"\b(FE\d+)\b", re.IGNORECASE)
_COMPARE_PAIR_RE = re.compile(
    r"\burutan\s*(\d+)\s*(?:dan|dengan|vs|&|serta)\s*urutan\s*(\d+)\b",
    re.IGNORECASE,
)
_RELIMIT_RE = re.compile(
    r"\b(?:hanya|tampilkan)\s*(?:top\s*)?(\d+)\s*saja\b",
    re.IGNORECASE,
)


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

_DRILL_MATERIAL_TERMS = (
    "produk",
    "product",
    "material",
    "sku",
    "plu",
    "item",
    "breakdown",
    "break down",
    "rincian",
    "detail",
)

_FILTER_TERMS = ("based on", "berdasarkan", "untuk", "for", "di ", "cabang", "branch", "dc ")

# metric prefix / name → (domain_id, default grain column)
_METRIC_DOMAIN_GRAIN: dict[str, tuple[str, str]] = {
    "b2b_branch_sell_out": ("b2b", "branch"),
    "b2b_branch": ("b2b", "branch"),
    "material_sell_out": ("b2b", "material"),
    "b2b_material": ("b2b", "material"),
    "material_sell_in": ("sales", "material"),
    "sales_office_material": ("sales", "material"),
    "sales_office_sell_in": ("sales", "sales_office"),
    "sales_office": ("sales", "sales_office"),
    "sat_dc_stock": ("stock_sat", "dcname"),
    "sat_store_stock": ("stock_sat", "division"),
    "sat_oos": ("sat_oos", "material_code"),
    "service_fill_rate": ("service_level", "sales_off"),
    "sales_office_service": ("service_level", "sales_off"),
    "average_picking": ("picking", "sales_off"),
    "average_unloading": ("unloading", "sales_off"),
    "promo_": ("promo", "material"),
    "warehouse_stock": ("stock_tempo", "material"),
    "stock_tempo": ("stock_tempo", "material"),
}


def infer_domain_and_grain(metric: str | None, entity_dimension: str | None) -> tuple[str | None, str | None]:
    if not metric:
        return None, entity_dimension
    lowered = metric.casefold()
    for prefix, (domain_id, grain) in _METRIC_DOMAIN_GRAIN.items():
        if prefix in lowered:
            return domain_id, entity_dimension or grain
    return None, entity_dimension


def build_analysis_context(
    *,
    metric: str | None,
    dimensions: list[str] | None,
    entity_dimension: str | None,
    ranked_entities: list[dict[str, Any]],
    last_question: str,
) -> dict[str, Any]:
    domain_id, grain = infer_domain_and_grain(metric, entity_dimension)
    catalog: list[dict[str, Any]] = []
    for item in ranked_entities:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        dim = str(item.get("dimension") or grain or "entity")
        catalog.append(
            {
                "rank": item.get("rank"),
                "entity_type": dim,
                "id": str(item["id"]),
                "display": str(item["id"]),
                "metric_value": item.get("metric_value"),
            }
        )
    return {
        "domain_id": domain_id,
        "last_metric": metric,
        "last_dimensions": list(dimensions or []),
        "active_grain": grain,
        "entity_dimension": entity_dimension,
        "result_catalog": catalog,
        "last_question": last_question.strip(),
        "time_scope": "Q4_2024",
    }


def analysis_context_from_history(history: list[dict]) -> dict[str, Any]:
    anchor = (
        _last_governed_chart_turn(history)
        or _last_governed_success_turn(history)
        or (history[-1] if history else None)
    )
    if not anchor:
        return {}
    stored = anchor.get("session_frame") if isinstance(anchor.get("session_frame"), dict) else {}
    ctx = stored.get("analysis_context")
    if isinstance(ctx, dict) and ctx.get("last_metric"):
        return ctx
    metric = stored.get("last_metric")
    ranked = list(stored.get("ranked_entities") or [])
    if not ranked:
        ranked = _ranked_entities_from_rows(_rows_for_chart_follow_up(anchor))
    if not metric:
        metric = infer_governed_metric_from_turn(anchor, ranked_entities=ranked)
    if not metric and not ranked:
        return {}
    entity_dimension = stored.get("entity_dimension")
    if not entity_dimension and ranked:
        entity_dimension = ranked[0].get("dimension")
    return build_analysis_context(
        metric=str(metric) if metric else None,
        dimensions=list(stored.get("last_dimensions") or []),
        entity_dimension=str(entity_dimension) if entity_dimension else None,
        ranked_entities=ranked,
        last_question=str(stored.get("last_question") or anchor.get("question") or ""),
    )


def _normalize(text: str) -> str:
    return " ".join(text.casefold().replace("–", "-").split())


def _parse_top_n(question: str, default: int = 5) -> int:
    match = _TOP_N_RE.search(question)
    if match:
        return max(1, min(25, int(match.group(1))))
    return default


def _wants_material_drill(question: str) -> bool:
    lowered = _normalize(question)
    return any(term in lowered for term in _DRILL_MATERIAL_TERMS)


def _parse_rank_index(question: str) -> int | None:
    lowered = _normalize(question)
    match = _RANK_N_RE.search(lowered)
    if match:
        return int(match.group(1))
    if any(t in lowered for t in ("pertama", "paling atas", "teratas", "top 1", "rank 1", "urutan 1")):
        return 1
    if any(t in lowered for t in ("paling jelek", "terjelek", "terburuk")) and any(
        t in lowered for t in ("cabang", "office", "sales", "fill", "service")
    ):
        return 1
    if any(t in lowered for t in ("kritis", "paling kritis", "paling rendah", "terendah")) and any(
        t in lowered for t in ("material", "stok", "stock", "cover")
    ):
        return 1
    if any(t in lowered for t in ("kelima", "ke lima", "ke-5", "urutan 5")):
        return 5
    if any(t in lowered for t in ("terakhir", "paling bawah")):
        return -1
    return None


def _catalog_by_rank(catalog: list[dict[str, Any]], rank: int) -> dict[str, Any] | None:
    if not catalog:
        return None
    if rank == -1:
        return catalog[-1]
    for item in catalog:
        if item.get("rank") == rank:
            return item
    if 1 <= rank <= len(catalog):
        return catalog[rank - 1]
    return None


def _parse_compare_ranks(question: str) -> tuple[int, int] | None:
    lowered = _normalize(question)
    pair = _COMPARE_PAIR_RE.search(lowered)
    if pair:
        return int(pair.group(1)), int(pair.group(2))
    if "urutan 1" in lowered and "urutan 2" in lowered:
        return 1, 2
    return None


def _wants_plant_breakdown(question: str) -> bool:
    lowered = _normalize(question)
    return "per plant" in lowered or "by plant" in lowered or "per pabrik" in lowered


def _wants_branch_contribution_drill(question: str) -> bool:
    lowered = _normalize(question)
    return any(t in lowered for t in ("dc mana", "cabang mana", "kontribusi", "branch mana"))


def _wants_sell_in_crosscheck(question: str) -> bool:
    lowered = _normalize(question)
    return any(t in lowered for t in ("sell-in", "sell in", "penjualan tempo", "billing"))


def _bind_entity_from_catalog(question: str, catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not catalog:
        return None
    lowered = _normalize(question)
    rank = _parse_rank_index(question)
    if rank is not None:
        bound = _catalog_by_rank(catalog, rank)
        if bound:
            return bound
    # Rank references (legacy phrases)
    if any(t in lowered for t in ("pertama", "paling atas", "teratas", "rank 1", "urutan 1", "top 1")):
        for item in catalog:
            if item.get("rank") == 1:
                return item
    if any(t in lowered for t in ("terakhir", "paling bawah")):
        return catalog[-1]
    # Substring match on entity id (e.g. palembang → DC Palembang)
    for item in catalog:
        eid = _normalize(str(item.get("id") or ""))
        if not eid:
            continue
        tokens = [t for t in re.split(r"[\s_/\-]+", eid) if len(t) >= 4]
        for token in tokens:
            if token in lowered:
                return item
        if eid in lowered or lowered in eid:
            return item
    # "cabang X" / "branch X" single token
    match = re.search(
        r"\b(?:cabang|branch|dc)\s+([^,]+?)(?:\s*,|\s+top\b|\s+based\b|\s+produk\b|\s+product\b|$)",
        lowered,
        re.IGNORECASE,
    )
    if match:
        phrase = match.group(1).strip()
        for item in catalog:
            if phrase in _normalize(str(item.get("id") or "")):
                return item
        for token in re.split(r"[\s_/\-]+", phrase):
            if len(token) < 4:
                continue
            for item in catalog:
                if token in _normalize(str(item.get("id") or "")):
                    return item
    return None


@dataclass
class FollowUpPlan:
    intent: str
    filter_entity: dict[str, Any] | None
    to_grain: str | None
    limit: int | None
    domain_id: str | None
    from_grain: str | None
    compare_entities: list[dict[str, Any]] | None = None
    filter_entities: list[dict[str, Any]] | None = None
    breakdown_dimension: str | None = None
    metric_override: str | None = None


def _resolve_follow_up_plan(
    question: str,
    ctx: dict[str, Any],
    understanding: "TurnUnderstanding | None",
) -> FollowUpPlan | None:
    if not ctx.get("last_metric"):
        return None
    from app.services.session_context import is_referential_follow_up

    plan = plan_follow_up(question, ctx)
    if plan:
        return plan
    referential = is_referential_follow_up(question) or bool(
        understanding and understanding.referential_follow_up
    )
    if not referential:
        return None
    if understanding and understanding.referential_follow_up:
        return plan_from_understanding(understanding, ctx)
    return None


def plan_from_understanding(u: "TurnUnderstanding", ctx: dict[str, Any]) -> FollowUpPlan | None:
    if not u.referential_follow_up or not ctx.get("last_metric"):
        return None
    catalog = list(ctx.get("result_catalog") or [])
    filter_entity: dict[str, Any] | None = None
    if u.follow_up_entity_id:
        eid = u.follow_up_entity_id.strip()
        for item in catalog:
            sid = str(item.get("id") or "").strip()
            if sid == eid or eid.casefold() in sid.casefold():
                filter_entity = item
                break
        if filter_entity is None:
            dim = u.follow_up_entity_dimension or ctx.get("active_grain") or "branch"
            filter_entity = {
                "id": eid,
                "entity_type": dim,
                "dimension": dim,
                "rank": u.follow_up_rank,
            }
    elif u.follow_up_rank and catalog:
        for item in catalog:
            if item.get("rank") == u.follow_up_rank:
                filter_entity = item
                break
        if filter_entity is None and 1 <= int(u.follow_up_rank) <= len(catalog):
            filter_entity = catalog[int(u.follow_up_rank) - 1]

    to_grain: str | None = "material" if u.follow_up_material_drill else None
    limit: int | None = u.follow_up_top_n if u.follow_up_material_drill else None
    if u.follow_up_material_drill and not limit:
        limit = 5
    intent = "drill_down" if to_grain else "continue"
    if filter_entity and not to_grain:
        intent = "filter_entity"
    if not filter_entity and not to_grain:
        return None
    return FollowUpPlan(
        intent=intent,
        filter_entity=filter_entity,
        to_grain=to_grain,
        limit=limit,
        domain_id=str(ctx.get("domain_id")) if ctx.get("domain_id") else None,
        from_grain=str(ctx.get("active_grain") or ctx.get("entity_dimension") or "") or None,
    )


def plan_follow_up(question: str, ctx: dict[str, Any]) -> FollowUpPlan | None:
    if not ctx.get("last_metric"):
        return None
    catalog = list(ctx.get("result_catalog") or [])
    domain_id = ctx.get("domain_id")
    from_grain = ctx.get("active_grain") or ctx.get("entity_dimension")
    lowered = _normalize(question)
    last_metric = str(ctx.get("last_metric") or "")

    office_codes = re.findall(r"\b(0\d{3})\b", f"{ctx.get('last_question') or ''} {question}")
    office_codes = list(dict.fromkeys(office_codes))
    if len(office_codes) >= 2 and any(
        t in lowered
        for t in (
            "lebih lambat",
            "selisih",
            "mana yang lebih",
            "perbedaan",
            "bandingkan",
            "banding",
            "compare",
            " vs ",
            "versus",
        )
    ):
        ents: list[dict[str, Any]] = []
        for idx, code in enumerate(office_codes[:2]):
            ents.append(
                {
                    "rank": idx + 1,
                    "id": code,
                    "entity_type": "sales_office",
                    "dimension": "sales_office",
                }
            )
        return FollowUpPlan(
            intent="compare",
            filter_entity=None,
            to_grain=None,
            limit=None,
            domain_id=str(domain_id) if domain_id else None,
            from_grain="sales_office",
            compare_entities=ents,
        )

    mat_match = _MATERIAL_CODE_RE.search(question)
    if mat_match:
        code = mat_match.group(1).upper()
        filter_entity = {
            "id": code,
            "entity_type": "material",
            "dimension": "material",
            "rank": None,
        }
        metric_override = None
        if _wants_sell_in_crosscheck(question):
            metric_override = "material_sell_in_value"
        elif domain_id == "stock_tempo" or "stock" in last_metric.casefold() or "warehouse" in last_metric.casefold():
            metric_override = "material_warehouse_stock_quantity"
        return FollowUpPlan(
            intent="filter_entity",
            filter_entity=filter_entity,
            to_grain=None,
            limit=None,
            domain_id=str(domain_id) if domain_id else None,
            from_grain=str(from_grain) if from_grain else None,
            metric_override=metric_override,
        )

    if catalog and any(t in lowered for t in ("kontribusi", "persen kontribusi", "percent contribution")):
        if any(t in lowered for t in ("tiga produk", "3 produk", "top 3", "top3", "teratas tadi", "produk teratas")):
            return FollowUpPlan(
                intent="relimit",
                filter_entity=None,
                to_grain=None,
                limit=3,
                domain_id=str(domain_id) if domain_id else None,
                from_grain=str(from_grain) if from_grain else None,
            )

    relimit = _RELIMIT_RE.search(lowered)
    if relimit:
        return FollowUpPlan(
            intent="relimit",
            filter_entity=None,
            to_grain=None,
            limit=int(relimit.group(1)),
            domain_id=str(domain_id) if domain_id else None,
            from_grain=str(from_grain) if from_grain else None,
        )

    compare = _parse_compare_ranks(question)
    if compare and len(catalog) >= 2:
        a, b = compare
        ents = [_catalog_by_rank(catalog, a), _catalog_by_rank(catalog, b)]
        if ents[0] and ents[1]:
            return FollowUpPlan(
                intent="compare",
                filter_entity=None,
                to_grain=None,
                limit=None,
                domain_id=str(domain_id) if domain_id else None,
                from_grain=str(from_grain) if from_grain else None,
                compare_entities=[ents[0], ents[1]],
            )

    if _wants_plant_breakdown(question) and catalog:
        n = 3 if re.search(r"\btop\s*3\b", lowered) else 3
        subset = catalog[:n]
        return FollowUpPlan(
            intent="plant_breakdown",
            filter_entity=None,
            to_grain="plant",
            limit=None,
            domain_id=str(domain_id) if domain_id else None,
            from_grain=str(from_grain) if from_grain else None,
            filter_entities=subset,
            breakdown_dimension="plant",
        )

    filter_entity = _bind_entity_from_catalog(question, catalog)
    if (
        not filter_entity
        and catalog
        and any(t in lowered for t in ("lebih lambat", "paling lambat", "terlambat"))
        and any(t in last_metric.casefold() for t in ("unloading", "picking"))
    ):
        filter_entity = catalog[-1]
    to_grain: str | None = None
    limit: int | None = None
    intent = "continue"
    metric_override: str | None = None

    if filter_entity and _wants_branch_contribution_drill(question) and from_grain in ("material", "material_code"):
        return FollowUpPlan(
            intent="drill_down",
            filter_entity=filter_entity,
            to_grain="branch",
            limit=10,
            domain_id=str(domain_id) if domain_id else None,
            from_grain=str(from_grain) if from_grain else None,
            metric_override="b2b_branch_sell_out_value",
        )

    if filter_entity and _wants_sell_in_crosscheck(question) and domain_id == "stock_tempo":
        return FollowUpPlan(
            intent="filter_entity",
            filter_entity=filter_entity,
            to_grain=None,
            limit=None,
            domain_id=str(domain_id) if domain_id else None,
            from_grain=str(from_grain) if from_grain else None,
            metric_override="material_sell_in_value",
        )

    if any(t in lowered for t in ("company-wide", "company wide", "seluruh perusahaan", "companywide")):
        if "unloading" in last_metric.casefold() or "picking" in last_metric.casefold():
            return FollowUpPlan(
                intent="aggregate",
                filter_entity=None,
                to_grain=None,
                limit=None,
                domain_id=str(domain_id) if domain_id else None,
                from_grain=str(from_grain) if from_grain else None,
            )

    if _wants_material_drill(question):
        to_grain = "material"
        limit = _parse_top_n(question, default=3 if "3" in question else 5)
        intent = "drill_down"

    if filter_entity and not to_grain:
        intent = "filter_entity"

    if filter_entity and _wants_sell_in_crosscheck(question):
        metric_override = "material_sell_in_value"

    if not filter_entity and not to_grain:
        return None
    return FollowUpPlan(
        intent=intent,
        filter_entity=filter_entity,
        to_grain=to_grain,
        limit=limit,
        domain_id=str(domain_id) if domain_id else None,
        from_grain=str(from_grain) if from_grain else None,
        metric_override=metric_override,
    )


def _entity_predicate(entity: dict[str, Any], *, default_grain: str, flexible_branch: bool = False) -> str | None:
    dim = str(entity.get("entity_type") or entity.get("dimension") or default_grain)
    eid = str(entity.get("id") or "")
    if not eid:
        return None
    lit = _sql_string_literal(eid)
    if flexible_branch and dim == "branch":
        # Partner DC labels vary slightly between result table and Impala (e.g. "DC Palembang").
        return f"(d.branch = {lit} OR UPPER(d.branch) LIKE CONCAT('%', UPPER({lit}), '%'))"
    return f"d.{dim} = {lit}"


def _entities_in_predicate(entities: list[dict[str, Any]], *, default_grain: str) -> str | None:
    dim = default_grain
    ids: list[str] = []
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        dim = str(ent.get("entity_type") or ent.get("dimension") or dim)
        eid = str(ent.get("id") or "")
        if eid:
            ids.append(_sql_string_literal(eid))
    if not ids:
        return None
    if len(ids) == 1:
        return f"d.{dim} = {ids[0]}"
    return f"d.{dim} IN ({', '.join(ids)})"


def _drill_metric_and_dimensions(plan: FollowUpPlan, ctx: dict[str, Any]) -> tuple[str, list[str], list[str]] | None:
    """Return (metric, dimensions, extra_sql_predicates) for governed compile."""
    domain = plan.domain_id or ctx.get("domain_id")
    last_metric = str(plan.metric_override or ctx.get("last_metric") or "")
    default_grain = str(plan.from_grain or ctx.get("active_grain") or "branch")
    predicates: list[str] = []
    entity = plan.filter_entity

    if plan.intent == "relimit":
        dims = list(ctx.get("last_dimensions") or [])
        if not dims and default_grain:
            dims = [default_grain]
        return str(ctx.get("last_metric") or last_metric), dims, []

    if plan.intent == "aggregate":
        return last_metric, [], []

    if plan.intent == "compare" and plan.compare_entities:
        pred = _entities_in_predicate(plan.compare_entities, default_grain=default_grain)
        if pred:
            predicates.append(pred)
        grain = str(plan.compare_entities[0].get("dimension") or default_grain or "sales_office")
        if grain == "sales_office" and "unloading" in str(ctx.get("last_metric") or "").casefold():
            return "average_unloading_minutes", [grain], predicates
        if grain == "sales_office" and "picking" in str(ctx.get("last_metric") or "").casefold():
            return "average_picking_minutes", [grain], predicates
        if grain in ("sales_office", "sales_off") and any(
            term in str(ctx.get("last_metric") or last_metric).casefold()
            for term in ("sell_in", "billing", "sales_office", "material_sell_in")
        ):
            return "sales_office_sell_in_value", [grain], predicates
        dims = list(ctx.get("last_dimensions") or [grain])
        return str(ctx.get("last_metric") or last_metric), dims, predicates

    if plan.intent == "plant_breakdown" and plan.filter_entities:
        grain = str(plan.filter_entities[0].get("dimension") or "material")
        pred = _entities_in_predicate(plan.filter_entities, default_grain=grain)
        if pred:
            predicates.append(pred)
        if domain == "stock_tempo" or "stock_tempo" in last_metric.casefold():
            return "stock_tempo_total_qty", ["plant", "material"], predicates
        return last_metric, ["plant", grain], predicates

    if entity:
        pred = _entity_predicate(entity, default_grain=default_grain, flexible_branch=True)
        if pred:
            predicates.append(pred)

    if plan.to_grain == "branch" and entity:
        return "b2b_branch_sell_out_value", ["branch"], predicates

    if plan.to_grain == "plant" and entity:
        if domain == "stock_tempo" or "stock" in last_metric.casefold():
            return "stock_tempo_total_qty", ["plant"], predicates

    if plan.to_grain == "material":
        if domain == "service_level" or "service" in last_metric.casefold() or "fill_rate" in last_metric.casefold():
            off_dim = "sales_off"
            if entity:
                ed = str(entity.get("entity_type") or entity.get("dimension") or "")
                if ed in ("sales_off", "sales_office"):
                    off_dim = ed
            dims = ["material"]
            preds = list(predicates)
            if entity and preds:
                if off_dim == "sales_office":
                    preds = [p.replace("d.sales_office", "d.sales_off") for p in preds]
                    off_dim = "sales_off"
                dims.append(off_dim)
            return "sales_office_service_fill_rate", dims, preds
        if domain == "sales" or "sell_in" in last_metric.casefold():
            dims = ["material"]
            if entity and str(entity.get("entity_type") or "") in ("sales_office", "sales_off"):
                dims.append(str(entity["entity_type"]))
            return "sales_office_material_sell_in_value", dims, predicates
        if domain == "b2b" or "b2b" in last_metric.casefold() or "sell_out" in last_metric.casefold():
            # corr_b2b_material_plu is not reliably queryable in PoC Impala; use governed
            # material sell-out semantic (same family as management "top produk" questions).
            branch_predicates = [p for p in predicates if not p.casefold().startswith("d.branch")]
            return "material_sell_out_value", ["material"], branch_predicates
        if domain == "stock_sat":
            return "sat_store_stock_quantity", ["plu"], predicates
        if domain == "sat_oos":
            return "sat_oos_rate", ["material_code"], predicates
        return "material_sell_in_value", ["material"], predicates

    if plan.intent == "filter_entity" and entity:
        ent_dim = str(entity.get("entity_type") or entity.get("dimension") or default_grain)
        dims = list(ctx.get("last_dimensions") or [ent_dim])
        if ent_dim not in dims and len(dims) == 1 and dims[0] != ent_dim:
            dims = [ent_dim]
        return last_metric, dims, predicates

    return None


def build_follow_up_rewrite(question: str, ctx: dict[str, Any], plan: FollowUpPlan) -> str:
    parts = [
        f"Q4 2024 analytic follow-up on prior question: {ctx.get('last_question', '')[:160]}.",
        f"Prior governed metric: {ctx.get('last_metric')}; domain: {ctx.get('domain_id')}; grain: {ctx.get('active_grain')}.",
    ]
    if plan.filter_entity:
        ent = plan.filter_entity
        parts.append(
            f'Filter {ent.get("entity_type")} = "{ent.get("id")}" (rank {ent.get("rank")} from prior result table).'
        )
    if plan.to_grain == "material" and plan.limit:
        parts.append(
            f"Show top {plan.limit} materials/products by sales value consistent with prior measure family, grouped by material."
        )
    cabang = classify_cabang_grain(question, session_last_metric=str(ctx.get("last_metric") or ""))
    if cabang == "branch":
        parts.append("Interpret cabang as B2B partner branch (sell-out), not Tempo sales office sell-in.")
    elif cabang == "sales_office":
        parts.append("Interpret cabang as Tempo sales office (sell-in).")
    parts.append(f"Original user question: {question.strip()}")
    return " ".join(parts)


def try_follow_up_governed_resolution(
    question: str,
    analysis_context: dict[str, Any],
    understanding: "TurnUnderstanding | None" = None,
) -> dict[str, Any] | None:
    if not analysis_context:
        return None
    plan = _resolve_follow_up_plan(question, analysis_context, understanding)
    if not plan:
        return None
    routed = _drill_metric_and_dimensions(plan, analysis_context)
    if not routed:
        return None
    metric, dimensions, predicates = routed
    dimension_mismatch: list[str] = []
    if plan.filter_entity and plan.to_grain == "material" and (
        plan.domain_id == "b2b"
        or "b2b" in str(analysis_context.get("last_metric") or "").casefold()
    ):
        # No governed branch×material sell-out view in Q4 PoC; rank is company material sell-out.
        dimension_mismatch = ["branch"]
    payload: dict[str, Any] = {
        "status": "resolved",
        "metric": metric,
        "matched_alias": "follow_up_context",
        "dimensions": dimensions,
        "dimension_mismatch": dimension_mismatch,
        "follow_up_entity_filters": predicates,
        "follow_up_plan": {
            "intent": plan.intent,
            "to_grain": plan.to_grain,
            "limit": plan.limit,
        },
    }
    if plan.intent == "filter_entity" and plan.filter_entity and plan.filter_entity.get("id"):
        payload["follow_up_catalog_entity"] = dict(plan.filter_entity)
    return payload


def try_rewrite_follow_up_question(
    question: str,
    history: list[dict],
    understanding: "TurnUnderstanding | None" = None,
) -> str | None:
    ctx = analysis_context_from_history(history)
    if not ctx:
        return None
    plan = _resolve_follow_up_plan(question, ctx, understanding)
    if not plan:
        return None
    return build_follow_up_rewrite(question, ctx, plan)
