"""Structure & Integration Agent (TDD §8). Produces the dependency/call graph for the
interactive map (PRD Step 3) as React-Flow-ready ``{nodes, edges}``.

Prefers the graph already written to Neo4j by the ingestion pipeline
(``core.orchestrator.build_knowledge_base``); if that store is empty but source is on
disk, it builds the call graph on the fly from the parsed AST.
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent

log = logging.getLogger("imperium.agents.structure")


class StructureAgent(BaseAgent):
    name = "structure"
    role = "structure"  # → Cerebras (llm/routing.py)

    def run(self, ctx: AgentContext) -> dict:
        """Return the repository's structure map ({nodes, edges}) for the graph viewer."""
        graph = self._fetch_graph(ctx.repository_id)
        if not graph.get("nodes") and ctx.repo_path:
            graph = self._build_graph(ctx.repository_id, ctx.repo_path)
        return {"structure_map": graph, "findings": []}

    def _fetch_graph(self, repository_id: str) -> dict:
        try:
            from imperium.rkb.graph import repo_graph

            return repo_graph(repository_id) or {"nodes": [], "edges": []}
        except Exception as exc:  # noqa: BLE001
            log.debug("graph fetch failed: %s", exc)
            return {"nodes": [], "edges": []}

    def _build_graph(self, repository_id: str, repo_path: str) -> dict:
        try:
            from imperium.intelligence.call_graph import build_call_graph
            from imperium.intelligence.parser import parse_directory

            parsed = parse_directory(repo_path)
            return build_call_graph(parsed_files=parsed, repository_id=repository_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("call graph build failed: %s", exc)
            return {"nodes": [], "edges": []}
