"""Security Surface Agent (TDD §8). A tool-using agent that hunts vulnerable
patterns, insecure data handling, and risky dependencies, emitting
``Finding(category=security)``.

Runs on the ``security`` role (Cerebras). Uses the read-only engine tools to inspect
source and semantic memory rather than being handed pre-built context.
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent
from imperium.agents.parsing import parse_findings

log = logging.getLogger("imperium.agents.security")

_SECURITY_SYSTEM = (
    "You are an application security engineer auditing a codebase. Use your tools to "
    "read source, search semantic memory, and trace blast radius. Look for injection "
    "(SQL/command/template), insecure deserialization, hardcoded secrets, weak crypto, "
    "missing authz checks, unsafe file/path handling, and risky dependencies. Report "
    "only concrete, evidence-backed issues. Respond with ONLY a JSON array: "
    '[{"category": "security", "title": "...", "detail": "...", '
    '"confidence": 0.0, "locations": ["file:line"]}]'
)

_SECURITY_TASK = (
    "Audit this repository for security vulnerabilities. Gather evidence with your "
    "tools first, then return the findings JSON."
)


class SecurityAgent(BaseAgent):
    name = "security"
    role = "security"  # → Cerebras

    def run(self, ctx: AgentContext) -> dict:
        """Audit the repository and return security findings."""
        try:
            from imperium.agents.agent_factory import run_tool_agent

            text = run_tool_agent(self.role, _SECURITY_SYSTEM, _SECURITY_TASK, ctx)
        except Exception as exc:  # noqa: BLE001
            log.warning("Security agent could not run: %s", exc)
            return {"findings": []}

        findings = parse_findings(text, default_category="security", default_confidence=0.6)
        return {"findings": [f.model_dump() for f in findings]}
