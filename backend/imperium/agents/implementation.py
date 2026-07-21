"""Implementation Agent(s) (TDD §8, §9). Executes approved changes per category in
ISOLATED branches, commits traceable to the originating to-do item (PRD Step 8).

TODO(team): branch-per-category, apply LLM-generated edits, link commit → decision.
Never touch main (PRD §14).
"""
from __future__ import annotations

from imperium.agents.base import AgentContext, BaseAgent


class ImplementationAgent(BaseAgent):
    name = "implementation"
    role = "implementation"  # → Mistral Codestral

    def run(self, ctx: AgentContext) -> dict:
        raise NotImplementedError("implementation agent — team task")
