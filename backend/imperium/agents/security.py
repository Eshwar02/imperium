"""Security Agent (TDD §8). Drives intelligence.security_scanner; emits Findings(category=security)."""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent
from imperium.api.schemas import Category, Finding

log = logging.getLogger("imperium.agents.security")


class SecurityAgent(BaseAgent):
    name = "security"
    role = "security"  # → Cerebras

    def run(self, ctx: AgentContext) -> dict:
        """Scan the repository for security vulnerabilities and emit Findings."""
        repo_path = ctx.repo_path

        if not repo_path:
            log.warning("SecurityAgent: no repo_path for %s", ctx.repository_id)
            return {"findings": []}

        try:
            from imperium.intelligence.security_scanner import scan

            findings = scan(repo_path)
            log.info(
                "SecurityAgent: %d findings for %s", len(findings), ctx.repository_id
            )
            return {"findings": [f.model_dump() for f in findings]}
        except Exception as exc:  # noqa: BLE001
            log.warning("Security scan failed: %s", exc)
            return {"findings": []}
