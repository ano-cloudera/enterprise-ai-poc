"""Load tempo_domain_graph.yaml into Neo4j (business ontology)."""

from __future__ import annotations

from typing import Any, Literal

from app.semantic.domain_graph import load_domain_graph

NodeKind = Literal["intent", "clarify"]

SCHEMA_CYPHER = """
CREATE CONSTRAINT domain_id IF NOT EXISTS FOR (d:Domain) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT metric_name IF NOT EXISTS FOR (m:Metric) REQUIRE m.name IS UNIQUE;
CREATE CONSTRAINT grain_id IF NOT EXISTS FOR (g:EntityGrain) REQUIRE g.id IS UNIQUE;
CREATE CONSTRAINT term_norm IF NOT EXISTS FOR (t:Term) REQUIRE t.normalized IS UNIQUE;
CREATE CONSTRAINT intent_id IF NOT EXISTS FOR (i:IntentRule) REQUIRE i.id IS UNIQUE;
CREATE CONSTRAINT journey_id IF NOT EXISTS FOR (j:Journey) REQUIRE j.id IS UNIQUE;
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:EntityType) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT clarify_id IF NOT EXISTS FOR (c:ClarificationIntent) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT drill_id IF NOT EXISTS FOR (p:DrillPath) REQUIRE p.id IS UNIQUE;
"""

CLEAR_ONTOLOGY = """
MATCH (n)
WHERE n:Domain OR n:Metric OR n:EntityGrain OR n:Term OR n:IntentRule
   OR n:Journey OR n:EntityType OR n:ClarificationIntent OR n:ClarificationOption
   OR n:DrillPath OR n:PartnerScope OR n:AmbiguityRule OR n:IntentRoute OR n:KnowledgeMeta
DETACH DELETE n
"""


def _norm_term(text: str) -> str:
    return " ".join(str(text).casefold().replace("–", "-").split())


def _link_terms(
    tx: Any,
    node_id: str,
    rel: str,
    terms: list[Any],
    *,
    kind: NodeKind = "intent",
) -> None:
    label = "ClarificationIntent" if kind == "clarify" else "IntentRule"
    for term in terms or []:
        normalized = _norm_term(str(term))
        if not normalized:
            continue
        tx.run(
            f"""
            MATCH (i:{label} {{id: $id}})
            MERGE (t:Term {{normalized: $n}})
            SET t.text = coalesce(t.text, $raw)
            MERGE (i)-[:{rel}]->(t)
            """,
            id=node_id,
            n=normalized,
            raw=str(term).strip(),
        )


def seed_domain_graph(session: Any, *, clear: bool = False) -> dict[str, int]:
    graph = load_domain_graph()
    if clear:
        session.run(CLEAR_ONTOLOGY)
    for stmt in SCHEMA_CYPHER.strip().split(";"):
        line = stmt.strip()
        if line:
            session.run(line)

    scope = str(graph.get("scope") or "")
    join_policy = str(graph.get("join_policy") or "")

    def tx_work(tx: Any) -> None:
        tx.run(
            "MERGE (m:KnowledgeMeta {id: 'tempo'}) SET m.scope = $scope, m.join_policy = $jp, m.version = $v",
            scope=scope,
            jp=join_policy,
            v=int(graph.get("version") or 1),
        )

        for domain in graph.get("domains") or []:
            if not isinstance(domain, dict):
                continue
            did = str(domain.get("id") or "")
            if not did:
                continue
            tx.run(
                "MERGE (d:Domain {id: $id}) SET d.label = $label, d.note = $note",
                id=did,
                label=str(domain.get("label") or did),
                note=str(domain.get("note") or "")[:2000],
            )
            for metric_name in domain.get("flagship_metrics") or []:
                mn = str(metric_name)
                tx.run("MERGE (m:Metric {name: $n})", n=mn)
                tx.run(
                    """
                    MATCH (d:Domain {id: $did}), (m:Metric {name: $n})
                    MERGE (d)-[:HAS_METRIC {flagship: true}]->(m)
                    """,
                    did=did,
                    n=mn,
                )
            for grain in domain.get("entity_grains") or []:
                gid = str(grain)
                tx.run("MERGE (g:EntityGrain {id: $id})", id=gid)
                tx.run(
                    """
                    MATCH (d:Domain {id: $did}), (g:EntityGrain {id: $gid})
                    MERGE (d)-[:USES_GRAIN]->(g)
                    """,
                    did=did,
                    gid=gid,
                )
            for term in domain.get("business_terms") or []:
                n = _norm_term(str(term))
                if not n:
                    continue
                tx.run("MERGE (t:Term {normalized: $n}) SET t.text = $raw", n=n, raw=str(term).strip())
                tx.run(
                    """
                    MATCH (d:Domain {id: $did}), (t:Term {normalized: $n})
                    MERGE (t)-[:IMPLIES_DOMAIN]->(d)
                    """,
                    did=did,
                    n=n,
                )

        for ent in graph.get("entities") or []:
            if not isinstance(ent, dict):
                continue
            eid = str(ent.get("id") or "")
            if not eid:
                continue
            tx.run(
                "MERGE (e:EntityType {id: $id}) SET e.label = $label, e.code_hint = $hint",
                id=eid,
                label=str(ent.get("label") or eid),
                hint=str(ent.get("code_hint") or ""),
            )
            for did in ent.get("domain_ids") or []:
                tx.run(
                    """
                    MATCH (e:EntityType {id: $eid}), (d:Domain {id: $did})
                    MERGE (e)-[:USED_IN]->(d)
                    """,
                    eid=eid,
                    did=str(did),
                )

        for journey in graph.get("journeys") or []:
            if not isinstance(journey, dict):
                continue
            jid = str(journey.get("id") or "")
            if not jid:
                continue
            tx.run(
                """
                MERGE (j:Journey {id: $id})
                SET j.label = $label, j.source_view = $sv, j.grain = $grain, j.dataset = $ds
                """,
                id=jid,
                label=str(journey.get("label") or jid),
                sv=str(journey.get("source_view") or ""),
                grain=str(journey.get("grain") or ""),
                ds=str(journey.get("dataset") or ""),
            )
            fd = str(journey.get("from_domain") or "")
            td = str(journey.get("to_domain") or "")
            if fd:
                tx.run(
                    "MATCH (j:Journey {id: $id}), (d:Domain {id: $did}) MERGE (j)-[:FROM]->(d)",
                    id=jid,
                    did=fd,
                )
            if td:
                tx.run(
                    "MATCH (j:Journey {id: $id}), (d:Domain {id: $did}) MERGE (j)-[:TO]->(d)",
                    id=jid,
                    did=td,
                )

        disambig = (graph.get("disambiguation") or {}).get("cabang") or {}
        if isinstance(disambig, dict):
            tx.run(
                "MERGE (a:AmbiguityRule {id: 'cabang'}) SET a.default_grain = $dg",
                dg=str(disambig.get("default_grain") or "sales_office"),
            )
            prefer_so = (disambig.get("prefer_sales_office") or {}).get("terms") or []
            prefer_br = (disambig.get("prefer_branch") or {}).get("terms") or []
            for term in prefer_so:
                n = _norm_term(str(term))
                if not n:
                    continue
                tx.run("MERGE (t:Term {normalized: $n})", n=n)
                tx.run(
                    """
                    MATCH (a:AmbiguityRule {id: 'cabang'}), (t:Term {normalized: $n})
                    MERGE (a)-[:PREFER_SALES_OFFICE_WHEN]->(t)
                    """,
                    n=n,
                )
            for term in prefer_br:
                n = _norm_term(str(term))
                if not n:
                    continue
                tx.run("MERGE (t:Term {normalized: $n})", n=n)
                tx.run(
                    """
                    MATCH (a:AmbiguityRule {id: 'cabang'}), (t:Term {normalized: $n})
                    MERGE (a)-[:PREFER_BRANCH_WHEN]->(t)
                    """,
                    n=n,
                )

        partner = (graph.get("partner_scope") or {}).get("alfamart") or {}
        if isinstance(partner, dict):
            tx.run(
                """
                MERGE (p:PartnerScope {id: 'alfamart'})
                SET p.meaning = $m, p.not_a_branch_filter = $nb
                """,
                m=str(partner.get("meaning") or "")[:2000],
                nb=bool(partner.get("not_a_branch_filter")),
            )
            tx.run(
                "MATCH (p:PartnerScope {id: 'alfamart'}), (d:Domain {id: 'b2b'}) MERGE (p)-[:SCOPES]->(d)"
            )
            tx.run(
                "MATCH (p:PartnerScope {id: 'alfamart'}), (d:Domain {id: 'stock_sat'}) MERGE (p)-[:SCOPES]->(d)"
            )

        for idx, route in enumerate(graph.get("intent_routes") or []):
            if not isinstance(route, dict):
                continue
            rid = f"route_{idx}"
            tx.run(
                """
                MERGE (r:IntentRoute {id: $id})
                SET r.primary_domain = $pd, r.metric_hint = $mh, r.dimension_hint = $dh
                """,
                id=rid,
                pd=str(route.get("primary_domain") or ""),
                mh=str(route.get("metric_hint") or ""),
                dh=str(route.get("dimension_hint") or ""),
            )
            for term in route.get("match_terms") or []:
                n = _norm_term(str(term))
                if not n:
                    continue
                tx.run("MERGE (t:Term {normalized: $n})", n=n)
                tx.run(
                    "MATCH (r:IntentRoute {id: $id}), (t:Term {normalized: $n}) MERGE (r)-[:MATCH_TERM]->(t)",
                    id=rid,
                    n=n,
                )

        for intent in graph.get("governed_intents") or []:
            if not isinstance(intent, dict):
                continue
            iid = str(intent.get("id") or intent.get("resolved_by") or "")
            if not iid:
                continue
            tx.run(
                """
                MERGE (i:IntentRule {id: $id})
                SET i.phase = 'first_turn', i.resolved_by = $rb, i.metric = $metric, i.priority = $pri
                """,
                id=iid,
                rb=str(intent.get("resolved_by") or iid),
                metric=str(intent.get("metric") or ""),
                pri=int(intent.get("priority") or 100),
            )
            for dim in intent.get("dimensions") or []:
                gid = str(dim)
                tx.run("MERGE (g:EntityGrain {id: $id})", id=gid)
                tx.run(
                    "MATCH (i:IntentRule {id: $id}), (g:EntityGrain {id: $gid}) MERGE (i)-[:WITH_DIMENSION]->(g)",
                    id=iid,
                    gid=gid,
                )
            metric = str(intent.get("metric") or "")
            if metric:
                tx.run("MERGE (m:Metric {name: $n})", n=metric)
                tx.run(
                    "MATCH (i:IntentRule {id: $id}), (m:Metric {name: $n}) MERGE (i)-[:RESOLVES_TO]->(m)",
                    id=iid,
                    n=metric,
                )
            _link_terms(tx, iid, "REQUIRES_ALL", list(intent.get("all_terms") or []))
            _link_terms(tx, iid, "REQUIRES_ANY", list(intent.get("any_terms") or []))
            _link_terms(tx, iid, "UNLESS_ANY", list(intent.get("unless_terms") or []))

        for intent in graph.get("follow_up_intents") or []:
            if not isinstance(intent, dict):
                continue
            iid = str(intent.get("id") or "")
            if not iid:
                continue
            tx.run(
                """
                MERGE (i:IntentRule {id: $id})
                SET i.phase = 'follow_up', i.resolved_by = $rb, i.metric = $metric, i.priority = $pri
                """,
                id=iid,
                rb=str(intent.get("resolved_by") or iid),
                metric=str(intent.get("metric") or ""),
                pri=int(intent.get("priority") or 200),
            )
            sd = str(intent.get("session_domain") or "")
            if sd:
                tx.run(
                    "MATCH (i:IntentRule {id: $id}), (d:Domain {id: $did}) MERGE (i)-[:WHEN_SESSION_DOMAIN]->(d)",
                    id=iid,
                    did=sd,
                )
            for dim in intent.get("dimensions") or []:
                gid = str(dim)
                tx.run("MERGE (g:EntityGrain {id: $id})", id=gid)
                tx.run(
                    "MATCH (i:IntentRule {id: $id}), (g:EntityGrain {id: $gid}) MERGE (i)-[:WITH_DIMENSION]->(g)",
                    id=iid,
                    gid=gid,
                )
            metric = str(intent.get("metric") or "")
            if metric:
                tx.run("MERGE (m:Metric {name: $n})", n=metric)
                tx.run(
                    "MATCH (i:IntentRule {id: $id}), (m:Metric {name: $n}) MERGE (i)-[:RESOLVES_TO]->(m)",
                    id=iid,
                    n=metric,
                )
            _link_terms(tx, iid, "REQUIRES_ALL", list(intent.get("all_terms") or []))
            _link_terms(tx, iid, "REQUIRES_ANY", list(intent.get("any_terms") or []))
            _link_terms(tx, iid, "UNLESS_ANY", list(intent.get("unless_terms") or []))

        for intent in graph.get("clarification_intents") or []:
            if not isinstance(intent, dict):
                continue
            cid = str(intent.get("id") or "")
            if not cid:
                continue
            tx.run(
                """
                MERGE (c:ClarificationIntent {id: $id})
                SET c.reason = $reason, c.question = $question
                """,
                id=cid,
                reason=str(intent.get("reason") or cid),
                question=str(intent.get("question") or "").strip()[:4000],
            )
            _link_terms(tx, cid, "REQUIRES_ALL", list(intent.get("all_terms") or []), kind="clarify")
            _link_terms(tx, cid, "REQUIRES_ANY", list(intent.get("any_terms") or []), kind="clarify")
            _link_terms(tx, cid, "UNLESS_ANY", list(intent.get("unless_terms") or []), kind="clarify")
            for opt in intent.get("options") or []:
                if not isinstance(opt, dict):
                    continue
                om = str(opt.get("metric") or "")
                if not om:
                    continue
                oid = f"{cid}:{om}"
                tx.run(
                    """
                    MERGE (o:ClarificationOption {id: $oid})
                    SET o.metric = $m, o.label = $label
                    """,
                    oid=oid,
                    m=om,
                    label=str(opt.get("label") or om),
                )
                tx.run(
                    """
                    MATCH (c:ClarificationIntent {id: $cid}), (o:ClarificationOption {id: $oid})
                    MERGE (c)-[:OPTION]->(o)
                    """,
                    cid=cid,
                    oid=oid,
                )

        for idx, path in enumerate(graph.get("drill_paths") or []):
            if not isinstance(path, dict):
                continue
            pid = f"{path.get('domain')}_{path.get('from_grain')}_{path.get('to_grain')}_{idx}"
            tx.run(
                """
                MERGE (p:DrillPath {id: $id})
                SET p.domain = $dom, p.from_grain = $fg, p.to_grain = $tg, p.metric = $metric
                """,
                id=pid,
                dom=str(path.get("domain") or ""),
                fg=str(path.get("from_grain") or ""),
                tg=str(path.get("to_grain") or ""),
                metric=str(path.get("metric") or ""),
            )
            did = str(path.get("domain") or "")
            if did:
                tx.run(
                    "MATCH (p:DrillPath {id: $id}), (d:Domain {id: $did}) MERGE (p)-[:IN_DOMAIN]->(d)",
                    id=pid,
                    did=did,
                )

    session.execute_write(tx_work)

    counts = session.run(
        """
        RETURN
          count { (d:Domain) } AS domains,
          count { (m:Metric) } AS metrics,
          count { (i:IntentRule) } AS intents,
          count { (t:Term) } AS terms
        """
    ).single()
    return {
        "domains": int(counts["domains"]),
        "metrics": int(counts["metrics"]),
        "intents": int(counts["intents"]),
        "terms": int(counts["terms"]),
    }
