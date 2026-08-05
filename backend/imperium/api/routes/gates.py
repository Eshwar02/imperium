"""Human-in-the-Loop approval gates (TDD §7, PRD §9). Gate A + Gate B.

Extended for full HITL audit trail (§1.3):
  - Gate A/B votes are persisted as Decision rows (append-only, origin=human).
  - /clarifications/{repository_id}  — low-confidence business rule questions
  - /clarifications/{repository_id}/answer  — submit developer answers
  - /decisions/{repository_id}  — fetch full append-only decision log
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from imperium.api.ownership import require_owner
from imperium.api.schemas import GateRequest
from imperium.core.orchestrator import Orchestrator

router = APIRouter(tags=["gates"])


# ── Gate endpoints ────────────────────────────────────────────────────────────

@router.post("/gate-a")
def gate_a(req: GateRequest, request: Request) -> dict:
    """Gate A — pre-implementation. Per-category approve/reject/defer.

    Votes are persisted to the Decision log with origin=human.
    Only approved categories proceed to implementation.
    """
    require_owner(req.repository_id, request)
    orch = Orchestrator()
    return orch.apply_gate_a(req)


@router.post("/gate-b")
def gate_b(req: GateRequest, request: Request) -> dict:
    """Gate B — pre-merge. Reviews full diff + behavioral diff per category.

    Votes are persisted to the Decision log. Approved categories merge to integration.
    """
    require_owner(req.repository_id, request)
    orch = Orchestrator()
    return orch.apply_gate_b(req)


# ── Clarification endpoints ───────────────────────────────────────────────────

@router.get("/clarifications/{repository_id}")
def clarifications(repository_id: str, request: Request) -> dict:
    """Return pending clarification questions for low-confidence business rules (TDD §7).

    Questions come from BusinessRule rows where confidence < threshold and verified=False.
    """
    require_owner(repository_id, request)
    orch = Orchestrator()
    return {"repository_id": repository_id, "questions": orch.pending_clarifications(repository_id)}


class ClarificationAnswer(BaseModel):
    rule_id: str
    answer: str
    approver: str | None = None


@router.post("/clarifications/{repository_id}/answer")
def answer_clarification(
    repository_id: str, body: ClarificationAnswer, request: Request
) -> dict:
    """Submit a developer answer to a clarification question.

    Marks the BusinessRule as verified and records the answer.
    """
    require_owner(repository_id, request)
    try:
        from imperium.rkb.store import get_session, verify_business_rule

        session = get_session()
        try:
            rule = verify_business_rule(session, body.rule_id, body.answer)
            if rule is None:
                raise HTTPException(status_code=404, detail=f"Rule {body.rule_id} not found")
        finally:
            session.close()

        return {
            "repository_id": repository_id,
            "rule_id": body.rule_id,
            "verified": True,
            "answer": body.answer,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Decision log endpoint ─────────────────────────────────────────────────────

@router.get("/decisions/{repository_id}")
def get_decisions(repository_id: str, request: Request) -> dict:
    """Return the append-only decision log for a repository (§1.3).

    Includes HITL votes, agent decisions, and prompt/answer pairs.
    """
    require_owner(repository_id, request)
    try:
        from imperium.rkb.store import get_decisions as _get_decisions
        from imperium.rkb.store import get_session

        session = get_session()
        try:
            decisions = _get_decisions(session, repository_id)
        finally:
            session.close()

        return {
            "repository_id": repository_id,
            "count": len(decisions),
            "decisions": [
                {
                    "id": d.id,
                    "category": d.category,
                    "change_summary": d.change_summary,
                    "rule_preserved": d.rule_preserved,
                    "alternative_rejected": d.alternative_rejected,
                    "gate": d.gate,
                    "origin": d.origin,
                    "approver": d.approver,
                    "approved_at": d.approved_at.isoformat() if d.approved_at else None,
                    "verdict": d.verdict,
                    "prompt_asked": d.prompt_asked,
                    "prompt_answer": d.prompt_answer,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in decisions
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
