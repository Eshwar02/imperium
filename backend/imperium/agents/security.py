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
        """Audit the repository: deterministic scan + LLM map-reduce, merged."""
        from imperium.agents.scale import _dedupe, run_scaled_findings

        findings = self._deterministic_findings(ctx)
        findings += run_scaled_findings(
            self.role,
            _SECURITY_SYSTEM,
            ctx,
            task_for_module=_module_task,
            whole_repo_task=_SECURITY_TASK,
            default_category="security",
            default_confidence=0.6,
        )
        return {"findings": _dedupe(findings)}

    def _deterministic_findings(self, ctx: AgentContext) -> list[dict]:
        """Fast regex scan — runs without an LLM, so it works even offline."""
        if not ctx.repo_path:
            return []
        try:
            from imperium.intelligence.security_scanner import scan

            return [f.model_dump() for f in scan(ctx.repo_path)]
        except Exception as exc:  # noqa: BLE001
            log.debug("deterministic security scan failed: %s", exc)
            return []
