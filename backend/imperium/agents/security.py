"""Security Surface Agent (TDD §8). A tool-using agent that hunts vulnerable
patterns, insecure data handling, and risky dependencies, emitting
``Finding(category=security)``.

Runs on the ``security`` role (Cerebras). Uses the read-only engine tools to inspect
source and semantic memory rather than being handed pre-built context.
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent

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


def _module_task(module) -> str:
    path = getattr(module, "path", "")
    name = getattr(module, "name", path)
    return (
        f"Audit the module '{name}' (path: {path}) for security vulnerabilities. Use "
        "read_source on its files, list_api_endpoints and list_data_access for exposure "
        "and data-access risk, and blast_radius for impact. Return findings JSON."
    )


class SecurityAgent(BaseAgent):
    name = "security"
    role = "security"  # → Cerebras

    def run(self, ctx: AgentContext) -> dict:
        """Audit the repository (map-reduce over modules) and return security findings."""
        from imperium.agents.scale import run_scaled_findings

        findings = run_scaled_findings(
            self.role,
            _SECURITY_SYSTEM,
            ctx,
            task_for_module=_module_task,
            whole_repo_task=_SECURITY_TASK,
            default_category="security",
            default_confidence=0.6,
        )
        return {"findings": findings}
