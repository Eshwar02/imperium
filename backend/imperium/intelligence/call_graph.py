"""Call Graph Builder (TDD §4). Produces nodes/edges for RKB graph + structure map.

TODO(team): resolve call sites across files, emit {nodes, edges} consumable by
rkb.graph.write_call_graph and the React Flow structure map.
"""
from __future__ import annotations

from imperium.intelligence.ast_builder import AstNode


def build_call_graph(asts: list[AstNode]) -> dict:
    """Return {"nodes": [...], "edges": [...]}. TODO(team)."""
    raise NotImplementedError("call graph — team task")
