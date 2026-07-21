"""Business-Logic Extraction Agent (TDD §8). Surfaces implicit rules (core value).

TODO(team): drive intelligence.business_rule_extractor; route low-confidence rules
to HITL clarifications; persist verified rules to RKB.
"""
from __future__ import annotations

from imperium.agents.base import AgentContext, BaseAgent


class BusinessLogicAgent(BaseAgent):
    name = "business_logic"
    role = "business_logic"  # → Nemotron primary, Mistral secondary check

    def run(self, ctx: AgentContext) -> dict:
        raise NotImplementedError("business-logic agent — team task")
