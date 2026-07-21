"""Research Agent (TDD §8, PRD Step 6). Cross-references external sources
(framework docs, changelogs, CVE feeds) to ground recommendations in current info.

TODO(team): web/tool retrieval; attach citations to Findings so recommendations
are not from stale training data alone.
"""
from __future__ import annotations

from imperium.agents.base import AgentContext, BaseAgent


class ResearchAgent(BaseAgent):
    name = "research"
    role = "research"  # → Gemini (long context)

    def run(self, ctx: AgentContext) -> dict:
        raise NotImplementedError("research agent — team task")
