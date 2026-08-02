"""Neo4j knowledge graph — architecture / call / dependency graph (TDD §5, §10).

Nodes: Repository, Module, File, Function, ApiEndpoint, DbTable, ExternalService.
Edges: CALLS, DEPENDS_ON, EXPOSES, READS, WRITES, INTEGRATES_WITH.

Implements the driver, node/edge writes (write_call_graph), blast-radius traversal,
and the layered structure-map reads (repo_graph, layer_graph, api_surface, ...).
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
    """MERGE nodes/edges from Call Graph Builder output into Neo4j.

    Each node dict must have: {id, kind, name, repository_id, ...extra}.
    Each edge dict must have: {source, target, type} where type is one of
    CALLS | DEPENDS_ON | EXPOSES | READS | WRITES | INTEGRATES_WITH.
    """
    driver = _driver()
    with driver.session() as session:
        # Upsert nodes
        for node in nodes:
            kind = node.get("kind", "Unknown")
            props = {k: v for k, v in node.items() if k != "kind"}
            props["repository_id"] = repository_id
            session.run(
                f"MERGE (n:{kind} {{id: $id}}) SET n += $props",
                id=node["id"],
                props=props,
            )

        # Upsert edges
        for edge in edges:
            rel_type = edge.get("type", "CALLS")
            session.run(
                f"""
                MATCH (a {{id: $source}}), (b {{id: $target}})
                MERGE (a)-[r:{rel_type}]->(b)
                """,
                source=edge["source"],
                target=edge["target"],
            )


def blast_radius(function_id: str, depth: int = 3) -> list[dict]:
    """Return all nodes that depend on function_id up to `depth` hops (callers/dependents).

    Traverses CALLS and DEPENDS_ON edges in reverse direction.
    Returns list of {id, kind, name, hops}.
    """
    driver = _driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH path = (start {id: $fid})<-[:CALLS|DEPENDS_ON*1..$depth]-(dependent)
            RETURN DISTINCT
                dependent.id AS id,
                labels(dependent)[0] AS kind,
                dependent.name AS name,
                length(path) AS hops
            ORDER BY hops
            """,
            fid=function_id,
            depth=depth,
        )
        return [dict(record) for record in result]


def query_dependents(node_id: str) -> list[dict]:
    """Return direct dependents of a node (1-hop blast radius)."""
    return blast_radius(node_id, depth=1)


def get_node(node_id: str) -> dict | None:
    """Fetch a single node by id."""
    driver = _driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (n {id: $id}) RETURN n",
            id=node_id,
        )
        record = result.single()
        return dict(record["n"]) if record else None


def repo_graph(repository_id: str) -> dict:
    """Return all nodes and edges for a repository as a structure map (React Flow)."""
    driver = _driver()
    with driver.session() as session:
        nodes_res = session.run(
            "MATCH (n {repository_id: $rid}) RETURN n",
            rid=repository_id,
        )
        edges_res = session.run(
            """
            MATCH (a {repository_id: $rid})-[r]->(b {repository_id: $rid})
            RETURN a.id AS source, b.id AS target, type(r) AS type
            """,
            rid=repository_id,
        )
        nodes = [dict(record["n"]) for record in nodes_res]
        edges = [dict(record) for record in edges_res]
        return {"nodes": nodes, "edges": edges}


def layer_graph(repository_id: str, rel_types: list[str] | None = None) -> dict:
    """Return the subgraph for specific relation types (a single graph *layer*).

    ``rel_types`` e.g. ["CALLS"], ["EXPOSES","CONSUMES"], ["READS","WRITES"],
    ["DEPENDS_ON"]. ``None`` returns all layers (same as ``repo_graph``).
    """
    if not rel_types:
        return repo_graph(repository_id)
    rel_pattern = "|".join(rel_types)
    driver = _driver()
    with driver.session() as session:
        edges_res = session.run(
            f"""
            MATCH (a {{repository_id: $rid}})-[r:{rel_pattern}]->(b {{repository_id: $rid}})
            RETURN a.id AS source, b.id AS target, type(r) AS type
            """,
            rid=repository_id,
        )
        edges = [dict(record) for record in edges_res]
        node_ids = {e["source"] for e in edges} | {e["target"] for e in edges}
        nodes: list[dict] = []
        if node_ids:
            nodes_res = session.run(
                "MATCH (n {repository_id: $rid}) WHERE n.id IN $ids RETURN n",
                rid=repository_id,
                ids=list(node_ids),
            )
            nodes = [dict(record["n"]) for record in nodes_res]
        return {"nodes": nodes, "edges": edges}


def api_surface(repository_id: str) -> dict:
    """The API graph layer: EXPOSES + CONSUMES edges between files and endpoints."""
    return layer_graph(repository_id, ["EXPOSES", "CONSUMES"])


def data_access(repository_id: str) -> dict:
    """The data graph layer: READS + WRITES edges between files and tables."""
    return layer_graph(repository_id, ["READS", "WRITES"])


def ping() -> dict[str, str]:
    try:
        _driver().verify_connectivity()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "error": str(exc)[:200]}
