"""Call Graph Builder (TDD §4). Produces nodes/edges for RKB graph + structure map.

Resolves call sites across files and emits {nodes, edges} consumable by
rkb.graph.write_call_graph and the React Flow structure map.

Strategy:
  1. Walk AST nodes to collect function/class definitions (nodes).
  2. Walk AST call nodes to resolve to known definitions (edges).
  3. Fall back to name-matching for cross-file resolution.
"""
from __future__ import annotations

import hashlib
import logging
import os

from imperium.intelligence.ast_builder import AstNode, build_all
from imperium.intelligence.parser import ParsedFile

log = logging.getLogger("imperium.intelligence.call_graph")


def _node_id(file_path: str, name: str, kind: str) -> str:
    raw = f"{file_path}::{kind}::{name}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _collect_definitions(asts: list[tuple[str, AstNode]]) -> dict[str, dict]:
    """Collect all function/class/method definitions → {name: node_dict}."""
    defs: dict[str, dict] = {}
    for file_path, root in asts:
        _walk_definitions(root, file_path, defs)
    return defs


def _walk_definitions(node: AstNode, file_path: str, defs: dict, parent: str = "") -> None:
    if node.kind in ("function", "method", "class"):
        full_name = f"{parent}.{node.name}" if parent else node.name
        nid = _node_id(file_path, full_name, node.kind)
        defs[full_name] = {
            "id": nid,
            "kind": node.kind.capitalize(),
            "name": full_name,
            "file": file_path,
            "line_start": node.span[0],
            "line_end": node.span[1],
        }
        for child in node.children:
            _walk_definitions(child, file_path, defs, parent=full_name)
    else:
        for child in node.children:
            _walk_definitions(child, file_path, defs, parent=parent)


def _collect_calls(node: AstNode, file_path: str, parent_name: str) -> list[tuple[str, str]]:
    """Return [(caller_name, callee_name)] from call nodes."""
    calls = []
    if node.kind == "call":
        calls.append((parent_name, node.name))
    new_parent = node.name if node.kind in ("function", "method", "class") else parent_name
    for child in node.children:
        calls.extend(_collect_calls(child, file_path, new_parent))
    return calls


def build_call_graph(
    asts: list[AstNode] | None = None,
    parsed_files: list[ParsedFile] | None = None,
    repository_id: str | None = None,
) -> dict:
    """Return {"nodes": [...], "edges": [...]}.

    Pass either pre-built AstNodes or ParsedFiles (will build ASTs internally).
    """
    if asts is None and parsed_files is not None:
        asts = build_all(parsed_files)
    if asts is None:
        return {"nodes": [], "edges": []}

    # Pair each AST with its source file path (stored in root.name for module nodes)
    ast_pairs = [(a.name if a.kind == "module" else str(i), a) for i, a in enumerate(asts)]

    # Collect all definitions
    defs = _collect_definitions(ast_pairs)

    nodes = list(defs.values())
    edges: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()

    # Build edges from call sites
    for file_path, root in ast_pairs:
        for top_child in root.children:
            # Walk calls within each definition
            if top_child.kind in ("function", "method", "class"):
                caller_name = top_child.name
                caller_def = defs.get(caller_name)
                if caller_def is None:
                    continue

                raw_calls = _collect_calls(top_child, file_path, caller_name)
                for _, callee_name in raw_calls:
                    callee_def = defs.get(callee_name)
                    if callee_def and callee_def["id"] != caller_def["id"]:
                        edge_key = (caller_def["id"], callee_def["id"])
                        if edge_key not in seen_edges:
                            seen_edges.add(edge_key)
                            edges.append({
                                "source": caller_def["id"],
                                "target": callee_def["id"],
                                "type": "CALLS",
                            })

    log.info("Call graph: %d nodes, %d edges", len(nodes), len(edges))

    if repository_id:
        try:
            from imperium.rkb.graph import write_call_graph

            write_call_graph(repository_id, nodes, edges)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not write call graph to Neo4j: %s", exc)

    return {"nodes": nodes, "edges": edges}
