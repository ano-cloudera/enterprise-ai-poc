"""Neo4j ontology tests (integration skipped unless NEO4J_ENABLED=true and bolt reachable)."""

from __future__ import annotations

import os

import pytest

from app.core.config import Settings
from app.knowledge.neo4j_seed import _norm_term
from app.services.neo4j_client import Neo4jKnowledgeClient


def test_norm_term_collapses_whitespace() -> None:
    assert _norm_term("  Paling   Laku ") == "paling laku"


@pytest.mark.skipif(os.environ.get("NEO4J_ENABLED", "").lower() not in ("1", "true", "yes"), reason="NEO4J_ENABLED not set")
def test_neo4j_governed_intents_match_yaml_count() -> None:
    from app.semantic.domain_graph import load_domain_graph

    settings = Settings(
        neo4j_enabled=True,
        neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", "tempo-graph-local"),
    )
    client = Neo4jKnowledgeClient(settings)
    if not client.ping():
        pytest.skip("Neo4j not reachable")
    yaml_count = len(load_domain_graph().get("governed_intents") or [])
    neo_count = len(client.list_governed_intents())
    assert neo_count == yaml_count
