"""Business-Logic Extraction Agent (TDD §8). Surfaces implicit business rules — the
core value of the system.

<<<<<<< HEAD
Drives intelligence.business_rule_extractor; routes low-confidence rules to HITL
clarifications; persists verified rules to RKB.
=======
Drives ``intelligence.business_rule_extractor``: it scans source for rule candidates,
enriches them with the ``business_logic`` LLM role (Nemotron primary, Mistral secondary
check), and persists them to the RKB registry. Low-confidence rules become HITL
clarifications via the orchestrator's ``pending_clarifications`` (already wired to the
registry's unverified rows).
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent
from imperium.api.schemas import Category, Finding

log = logging.getLogger("imperium.agents.business_logic")

log = logging.getLogger("imperium.agents.business_logic")


class BusinessLogicAgent(BaseAgent):
    name = "business_logic"
    role = "business_logic"  # → Nemotron primary, Mistral secondary check

    def run(self, ctx: AgentContext) -> dict:
<<<<<<< HEAD
        """Extract business rules, persist to RKB, route low-confidence rules to HITL."""
        repository_id = ctx.repository_id
        repo_path = ctx.repo_path

        if not repo_path:
            log.warning("BusinessLogicAgent: no repo_path for %s", repository_id)
            return {"findings": [], "rules_extracted": 0, "hitl_questions": 0}

        # 1. Extract rules from source files via AST + LLM enrichment
        findings: list[Finding] = []
        try:
            from imperium.intelligence.business_rule_extractor import extract_rules

            findings = extract_rules(
                repo_path=repo_path,
                repository_id=repository_id,
            )
            log.info(
                "BusinessLogicAgent: extracted %d rules from %s",
                len(findings), repository_id,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Business rule extraction failed: %s", exc)

        # 2. Count how many rules ended up below the HITL threshold
        hitl_count = self._count_hitl_pending(repository_id)

        return {
            "findings": [f.model_dump() for f in findings],
            "rules_extracted": len(findings),
            "hitl_questions": hitl_count,
        }

    def _count_hitl_pending(self, repository_id: str) -> int:
        """Return number of low-confidence rules awaiting HITL clarification."""
        try:
            from imperium.rkb.store import get_session, get_unverified_rules

            session = get_session()
            try:
                rules = get_unverified_rules(session, repository_id, threshold=0.70)
                return len(rules)
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.debug("HITL count failed: %s", exc)
            return 0
=======
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
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
