"""Neo4j knowledge graph — architecture / call / dependency graph (TDD §5, §10).

Nodes: Repository, Module, File, Function, ApiEndpoint, DbTable, ExternalService.
Edges: CALLS, DEPENDS_ON, EXPOSES, READS, WRITES, INTEGRATES_WITH.
Foundation: driver + ping. Graph writes are TODO(team).
"""
from __future__ import annotations

from functools import lru_cache

from imperium.config import get_settings


@lru_cache
def _driver():
    from neo4j import GraphDatabase

    s = get_settings()
    return GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))


def write_call_graph(repository_id: str, nodes: list[dict], edges: list[dict]) -> None:
    """TODO(team): MERGE nodes/edges from Call Graph Builder output."""
    raise NotImplementedError("RKB graph write — team task")


def blast_radius(function_id: str, depth: int = 3) -> list[dict]:
    """Change blast radius (TDD §9, §11): traverse dependents up to depth. TODO(team)."""
    raise NotImplementedError("blast radius traversal — team task")


def ping() -> dict[str, str]:
    try:
        _driver().verify_connectivity()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "error": str(exc)[:200]}
