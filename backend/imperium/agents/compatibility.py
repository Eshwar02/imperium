"""Compatibility Agent (TDD §8, PRD Step 9). Validates proposed + existing
integrations against current external API versions to pre-empt near-future breakage.

TODO(team): diff detected integration versions vs latest; flag deprecations.
"""
from __future__ import annotations

from imperium.agents.base import AgentContext, BaseAgent


class CompatibilityAgent(BaseAgent):
    name = "compatibility"
    role = "compatibility"  # → Cerebras primary, Groq fallback

    def run(self, ctx: AgentContext) -> dict:
        raise NotImplementedError("compatibility agent — team task")
