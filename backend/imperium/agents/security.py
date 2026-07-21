"""Security Surface Agent (TDD §8). Vulnerable patterns, CVE deps, insecure handling.

TODO(team): drive intelligence.security_scanner; emit Findings(category=security).
"""
from __future__ import annotations

from imperium.agents.base import AgentContext, BaseAgent


class SecurityAgent(BaseAgent):
    name = "security"
    role = "security"  # → Cerebras

    def run(self, ctx: AgentContext) -> dict:
        raise NotImplementedError("security agent — team task")
