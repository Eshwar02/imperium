"""Structure & Integration Agent (TDD §8). Builds dependency/call graph + integration
catalogue for the interactive map (PRD Step 3).

TODO(team): drive intelligence.call_graph + api_mapper + db_mapper, write to
rkb.graph, return React-Flow-ready {nodes, edges}.
"""
from __future__ import annotations

from imperium.agents.base import AgentContext, BaseAgent


class StructureAgent(BaseAgent):
    name = "structure"
    role = "structure"  # → Cerebras (llm/routing.py)

    def run(self, ctx: AgentContext) -> dict:
        raise NotImplementedError("structure agent — team task")
