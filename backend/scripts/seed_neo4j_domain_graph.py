#!/usr/bin/env python3
"""Seed Neo4j from knowledge/tempo_domain_graph.yaml."""

from __future__ import annotations

import argparse
import sys

from app.core.config import get_settings
from app.knowledge.neo4j_seed import seed_domain_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed TEMPO domain graph into Neo4j")
    parser.add_argument("--clear", action="store_true", help="Remove ontology nodes before seed")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.neo4j_uri:
        print("NEO4J_URI is not set (e.g. bolt://localhost:7687)", file=sys.stderr)
        return 1
    password = settings.neo4j_password.get_secret_value()
    if not password:
        print("NEO4J_PASSWORD is not set", file=sys.stderr)
        return 1

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("Install neo4j driver: pip install neo4j", file=sys.stderr)
        return 1

    driver = GraphDatabase.driver(
        settings.neo4j_uri.strip(),
        auth=(settings.neo4j_user.strip(), password),
    )
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            counts = seed_domain_graph(session, clear=args.clear)
        print("Neo4j seed OK:", counts)
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
