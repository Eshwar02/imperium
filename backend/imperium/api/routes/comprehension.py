"""Comprehension checks (TDD §8, PRD §12.3) — the comprehension-drift surface.

Post-merge, non-blocking checks per owning engineer/module, plus each module's
comprehension score vs. its AI-authorship %. Read-only fetch + an answer route that
records a self-assessed comprehension score back onto the module (unflagging it once a
human demonstrably understands high-AI-authorship code).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from imperium.agents.base import AgentContext
from imperium.agents.comprehension import ComprehensionAgent
from imperium.core.healing import heal_call

log = logging.getLogger("imperium.api.comprehension")

router = APIRouter(tags=["comprehension"])


class ComprehensionAnswer(BaseModel):
    module_path: str
    comprehension_score: float  # 0.0-1.0, the engineer's demonstrated understanding
    decision_id: str | None = None
    answers: list[str] = []


@router.get("/comprehension/{repository_id}")
def get_comprehension(repository_id: str) -> dict:
    """Return comprehension checks for recent gate-B changes + per-module scores."""

    def _checks() -> list[dict]:
        agent = ComprehensionAgent()
        result = agent.run(AgentContext(repository_id=repository_id, repo_path=""))
        return result.get("checks", [])

    def _modules() -> list[dict]:
        from imperium.rkb.store import get_modules, get_session

        session = get_session()
        try:
            return [
                {
                    "name": m.name,
                    "path": m.path,
                    "ai_authorship_pct": m.ai_authorship_pct,
                    "comprehension_score": m.comprehension_score,
                    "flagged_for_review": m.flagged_for_review,
                }
                for m in get_modules(session, repository_id)
            ]
        finally:
            session.close()

    return {
        "repository_id": repository_id,
        "checks": heal_call("api.comprehension.checks", _checks, default=[]),
        "modules": heal_call("api.comprehension.modules", _modules, default=[]),
    }


@router.post("/comprehension/{repository_id}/answer")
def answer_comprehension(repository_id: str, ans: ComprehensionAnswer) -> dict:
    """Record a comprehension score for a module; unflag it if understanding is adequate."""

    def _run() -> dict:
        from imperium.rkb.store import get_modules, get_session

        session = get_session()
        try:
            module = next(
                (m for m in get_modules(session, repository_id) if m.path == ans.module_path),
                None,
            )
            if module is None:
                return {"recorded": False, "reason": "module not found"}
            module.comprehension_score = ans.comprehension_score
            # Understanding demonstrated → clear the comprehension-drift flag.
            if ans.comprehension_score >= 0.5:
                module.flagged_for_review = False
            session.commit()
            return {
                "recorded": True,
                "module_path": module.path,
                "comprehension_score": module.comprehension_score,
                "flagged_for_review": module.flagged_for_review,
            }
        finally:
            session.close()

    return heal_call("api.comprehension.answer", _run, default={"recorded": False})
