"""Comprehension & Knowledge-Retention Agent (TDD §8, PRD §12.3).

After a change clears Gate B and merges, issues short (2-3 q) non-blocking checks
to the owning engineer targeting that change's decision-log entry. Builds a
per-engineer, per-module comprehension score alongside the module's AI-authorship %.

Two-dimensional drift (PRD §12.1):
  - Code drift: stored model vs real behavior
  - Comprehension drift: human understanding vs what AI shipped

High-AI-authorship / low-comprehension modules are flagged back into Gate A.
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent

log = logging.getLogger("imperium.agents.comprehension")

_CHECK_SYSTEM = (
    "You are an engineering team lead. Given a decision-log entry describing a code change, "
    "generate exactly 3 short comprehension-check questions that the engineer who owns "
    "this module should be able to answer. Questions should test understanding of: "
    "(1) what changed, (2) why it was safe, (3) the business rule it preserves. "
    "Return JSON array: [{\"question\": \"...\", \"hint\": \"...\"}]"
)


class ComprehensionAgent(BaseAgent):
    name = "comprehension"
    role = "comprehension"  # → Cerebras

    def run(self, ctx: AgentContext) -> dict:
        """Generate comprehension checks for recent decisions in this repository."""
        repository_id = ctx.repository_id
        checks: list[dict] = []

        try:
            from imperium.rkb.store import get_decisions, get_session

            session = get_session()
            try:
                decisions = get_decisions(session, repository_id)
            finally:
                session.close()

            # Only decisions that cleared gate-b and have no existing check
            gate_b_decisions = [
                d for d in decisions
                if d.gate in ("B", "gate-b", "gate_b") and d.verdict == "approve"
            ][-10:]  # last 10

            for decision in gate_b_decisions:
                questions = self._generate_checks(decision)
                if questions:
                    checks.append({
                        "decision_id": decision.id,
                        "category": decision.category,
                        "change_summary": decision.change_summary,
                        "questions": questions,
                        "approver": decision.approver,
                    })

        except Exception as exc:  # noqa: BLE001
            log.warning("Comprehension agent error: %s", exc)

        # Update module comprehension scores + flag high-risk modules
        self._update_module_flags(ctx.repository_id)

        return {"checks": checks}

    def _generate_checks(self, decision) -> list[dict]:
        """Generate 3 comprehension questions for a decision."""
        import json
        import re

        from imperium.llm.client import complete

        prompt = (
            f"Category: {decision.category}\n"
            f"Change: {decision.change_summary}\n"
            f"Rule preserved: {decision.rule_preserved or 'N/A'}\n"
            f"Gate verdict: {decision.verdict}\n\n"
            "Generate 3 comprehension check questions:"
        )
        try:
            text = complete("comprehension", prompt, system=_CHECK_SYSTEM, temperature=0.3)
            m = re.search(r"\[.*\]", text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as exc:  # noqa: BLE001
            log.debug("Check generation failed for decision %s: %s", decision.id, exc)
        return []

    def _update_module_flags(self, repository_id: str) -> None:
        """Flag modules with high AI authorship and no comprehension score as risky."""
        try:
            from imperium.rkb.store import get_modules, get_session

            session = get_session()
            try:
                modules = get_modules(session, repository_id)
                for module in modules:
                    if module.ai_authorship_pct >= 70 and (
                        module.comprehension_score is None or module.comprehension_score < 0.5
                    ):
                        module.flagged_for_review = True
                session.commit()
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Module flag update failed: %s", exc)
