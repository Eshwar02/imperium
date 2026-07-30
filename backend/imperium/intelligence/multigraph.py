"""Multi-graph builder (TDD §4). Assembles the codebase's non-call graph layers —
**API**, **data/DB**, and **dependency** — and writes them into Neo4j alongside the
call graph, so agents can traverse the whole system through multiple relations.

Node kinds: ``File``, ``Endpoint``, ``Table``, ``Package``.
Edge types: ``EXPOSES`` / ``CONSUMES`` (API), ``READS`` / ``WRITES`` (data),
``DEPENDS_ON`` (dependency). All layers share the layer-agnostic
``rkb.graph.write_call_graph`` writer.

Each mapper is guarded independently: a failure in one layer never blocks the others.
"""
from __future__ import annotations

import logging

log = logging.getLogger("imperium.intelligence.multigraph")


def _file_of(site: str) -> str:
    return site.split(":", 1)[0] if site else "<unknown>"


def build_multigraph(repository_id: str, repo_path: str, write: bool = True) -> dict:
    """Build API + data + dependency graph layers; optionally write to Neo4j.

    Returns ``{nodes, edges, counts}``. Pure/testable when ``write=False``.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    counts = {"endpoints": 0, "tables": 0, "packages": 0, "edges": 0}

    def _node(node_id: str, kind: str, **props) -> None:
        nodes.setdefault(node_id, {"id": node_id, "kind": kind, "name": props.get("name", node_id), **props})

    def _file_node(path: str) -> str:
        nid = f"file:{path}"
        _node(nid, "File", name=path, path=path)
        return nid

    # ── API layer ──────────────────────────────────────────────────────────────
    try:
        from imperium.intelligence.api_mapper import map_apis

        for rec in map_apis(repo_path):
            ep_id = f"api:{rec['method']}:{rec['path']}"
            _node(ep_id, "Endpoint", name=f"{rec['method']} {rec['path']}", method=rec["method"], path=rec["path"])
            counts["endpoints"] += 1
            rel = "EXPOSES" if rec["kind"] == "exposed" else "CONSUMES"
            for site in rec.get("call_sites", []):
                edges.append({"source": _file_node(_file_of(site)), "target": ep_id, "type": rel})
    except Exception as exc:  # noqa: BLE001
        log.warning("API layer failed: %s", exc)

    # ── Data layer ─────────────────────────────────────────────────────────────
    try:
        from imperium.intelligence.db_mapper import map_database

        db = map_database(repo_path)
        for t in db.get("tables", []):
            _node(f"table:{t['name']}", "Table", name=t["name"], source=t.get("source", ""))
            counts["tables"] += 1
        for a in db.get("access", []):
            tid = f"table:{a['table']}"
            _node(tid, "Table", name=a["table"])
            rel = "READS" if a["op"] == "read" else "WRITES"
            edges.append({"source": _file_node(_file_of(a["location"])), "target": tid, "type": rel})
    except Exception as exc:  # noqa: BLE001
        log.warning("Data layer failed: %s", exc)

    # ── Dependency layer ───────────────────────────────────────────────────────
    try:
        from imperium.intelligence.dependency_mapper import map_dependencies

        for dep in map_dependencies(repo_path):
            name = dep.get("name") or dep.get("package")
            if not name:
                continue
            pid = f"pkg:{name}"
            _node(pid, "Package", name=name, version=dep.get("version", ""), ecosystem=dep.get("ecosystem", ""))
            counts["packages"] += 1
            src = dep.get("source") or "manifest"
            edges.append({"source": _file_node(_file_of(src)), "target": pid, "type": "DEPENDS_ON"})
    except Exception as exc:  # noqa: BLE001
        log.warning("Dependency layer failed: %s", exc)

    counts["edges"] = len(edges)
    node_list = list(nodes.values())

    if write and node_list:
        try:
            from imperium.rkb.graph import write_call_graph

            write_call_graph(repository_id, node_list, edges)
        except Exception as exc:  # noqa: BLE001
            log.warning("Multigraph write to Neo4j failed: %s", exc)

    return {"nodes": node_list, "edges": edges, "counts": counts}
