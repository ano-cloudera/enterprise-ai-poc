"""Neo4j client for TEMPO business knowledge graph (ontology from tempo_domain_graph.yaml)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.core.config import Settings


logger = logging.getLogger(__name__)


class Neo4jKnowledgeClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.uri = (settings.neo4j_uri or "").strip()
        self.user = (settings.neo4j_user or "neo4j").strip()
        self.password = settings.neo4j_password.get_secret_value()
        self.enabled = bool(settings.neo4j_enabled and self.uri and self.password)

    @property
    def configured(self) -> bool:
        return self.enabled

    def _driver(self) -> Any:
        from neo4j import GraphDatabase

        return GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def ping(self) -> bool:
        if not self.enabled:
            return False
        try:
            with self._driver() as driver:
                driver.verify_connectivity()
            return True
        except Exception:
            logger.info("neo4j_unreachable uri=%s", self.uri)
            return False

    def schema_summary(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "enabled": self.enabled,
            "uri": self.uri or None,
            "connected": False,
        }
        if not self.enabled:
            return base
        try:
            with self._driver() as driver:
                with driver.session() as session:
                    row = session.run(
                        """
                        OPTIONAL MATCH (d:Domain)
                        WITH count(d) AS domains
                        OPTIONAL MATCH (i:IntentRule)
                        WITH domains, count(i) AS intents
                        OPTIONAL MATCH (t:Term)
                        RETURN domains, intents, count(t) AS terms
                        """
                    ).single()
                    if row:
                        base.update(
                            {
                                "connected": True,
                                "domains": int(row["domains"]),
                                "intents": int(row["intents"]),
                                "terms": int(row["terms"]),
                            }
                        )
                    meta = session.run(
                        "MATCH (m:KnowledgeMeta {id: 'tempo'}) RETURN m.scope AS scope, m.version AS version"
                    ).single()
                    if meta:
                        base["scope"] = meta.get("scope")
                        base["version"] = meta.get("version")
        except Exception as exc:
            base["error"] = str(exc)[:200]
        return base

    def _intent_records(self, phase: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        query = """
        MATCH (i:IntentRule {phase: $phase})
        OPTIONAL MATCH (i)-[:WITH_DIMENSION]->(g:EntityGrain)
        WITH i, collect(DISTINCT g.id) AS dimensions
        OPTIONAL MATCH (i)-[:REQUIRES_ALL]->(a:Term)
        WITH i, dimensions, collect(DISTINCT a.normalized) AS all_terms
        OPTIONAL MATCH (i)-[:REQUIRES_ANY]->(y:Term)
        WITH i, dimensions, all_terms, collect(DISTINCT y.normalized) AS any_terms
        OPTIONAL MATCH (i)-[:UNLESS_ANY]->(u:Term)
        WITH i, dimensions, all_terms, any_terms, collect(DISTINCT u.normalized) AS unless_terms
        OPTIONAL MATCH (i)-[:WHEN_SESSION_DOMAIN]->(d:Domain)
        RETURN i.id AS id, i.metric AS metric, i.resolved_by AS resolved_by,
               i.priority AS priority, dimensions, all_terms, any_terms, unless_terms,
               d.id AS session_domain
        ORDER BY coalesce(i.priority, 100) DESC
        """
        out: list[dict[str, Any]] = []
        with self._driver() as driver:
            with driver.session() as session:
                for record in session.run(query, phase=phase):
                    out.append(
                        {
                            "id": record["id"],
                            "metric": record["metric"],
                            "resolved_by": record["resolved_by"],
                            "priority": record.get("priority"),
                            "dimensions": list(record["dimensions"] or []),
                            "all_terms": list(record["all_terms"] or []),
                            "any_terms": list(record["any_terms"] or []),
                            "unless_terms": list(record["unless_terms"] or []),
                            "session_domain": record.get("session_domain"),
                        }
                    )
        return out

    def list_governed_intents(self) -> list[dict[str, Any]]:
        return self._intent_records("first_turn")

    def list_follow_up_intents(self) -> list[dict[str, Any]]:
        return self._intent_records("follow_up")

    def list_clarification_intents(self) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        query = """
        MATCH (c:ClarificationIntent)
        OPTIONAL MATCH (c)-[:REQUIRES_ALL]->(a:Term)
        WITH c, collect(DISTINCT a.normalized) AS all_terms
        OPTIONAL MATCH (c)-[:REQUIRES_ANY]->(y:Term)
        WITH c, all_terms, collect(DISTINCT y.normalized) AS any_terms
        OPTIONAL MATCH (c)-[:UNLESS_ANY]->(u:Term)
        WITH c, all_terms, any_terms, collect(DISTINCT u.normalized) AS unless_terms
        OPTIONAL MATCH (c)-[:OPTION]->(o:ClarificationOption)
        RETURN c.id AS id, c.reason AS reason, c.question AS question,
               all_terms, any_terms, unless_terms,
               collect({metric: o.metric, label: o.label}) AS options
        """
        out: list[dict[str, Any]] = []
        with self._driver() as driver:
            with driver.session() as session:
                for record in session.run(query):
                    options = []
                    for opt in record["options"] or []:
                        if isinstance(opt, dict) and opt.get("metric"):
                            options.append({"metric": opt["metric"], "label": opt.get("label") or opt["metric"]})
                    out.append(
                        {
                            "id": record["id"],
                            "reason": record["reason"],
                            "question": record["question"],
                            "all_terms": list(record["all_terms"] or []),
                            "any_terms": list(record["any_terms"] or []),
                            "unless_terms": list(record["unless_terms"] or []),
                            "options": options,
                        }
                    )
        return out


@lru_cache(maxsize=1)
def get_neo4j_client(settings: Settings) -> Neo4jKnowledgeClient:
    return Neo4jKnowledgeClient(settings)
