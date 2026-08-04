"""Business-Logic Extraction Agent (TDD §8). Surfaces implicit business rules — the
core value of the system.

Drives ``intelligence.business_rule_extractor``: it scans source for rule candidates,
enriches them with the ``business_logic`` LLM role (Nemotron primary, Mistral secondary
check), and persists them to the RKB registry. Low-confidence rules become HITL
clarifications via the orchestrator's ``pending_clarifications`` (already wired to the
registry's unverified rows).
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent

log = logging.getLogger("imperium.agents.business_logic")


class BusinessLogicAgent(BaseAgent):
    name = "business_logic"
    role = "business_logic"  # → Nemotron primary, Mistral secondary check

    def run(self, ctx: AgentContext) -> dict:
        """Extract + persist business rules; return them as findings."""
        if not ctx.repo_path:
            log.info("No repo_path for business-logic extraction on %s", ctx.repository_id)
            return {"findings": []}

        try:
            from imperium.intelligence.business_rule_extractor import extract_rules

            findings = extract_rules(ctx.repo_path, repository_id=ctx.repository_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("Business-rule extraction failed: %s", exc)
            return {"findings": []}

        return {"findings": [f.model_dump() for f in findings]}
