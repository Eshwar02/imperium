"""Human-in-the-Loop approval gates (TDD §7, PRD §9). Gate A + Gate B."""
from __future__ import annotations

from fastapi import APIRouter

from imperium.api.schemas import GateRequest
from imperium.core.orchestrator import Orchestrator

router = APIRouter(tags=["gates"])


@router.post("/gate-a")
def gate_a(req: GateRequest) -> dict:
    """Gate A — pre-implementation. Per-category approve/reject/defer of the to-do list.

    TODO(team): record votes in RKB decision log; only approved categories proceed.
    """
    orch = Orchestrator()
    return orch.apply_gate_a(req)


@router.post("/gate-b")
def gate_b(req: GateRequest) -> dict:
    """Gate B — pre-merge. Reviews full diff + behavioral diff report, per category.

    TODO(team): gate on behavioral diff report; approved → merge to integration branch.
    """
    orch = Orchestrator()
    return orch.apply_gate_b(req)


@router.get("/clarifications/{repository_id}")
def clarifications(repository_id: str) -> dict:
    """Low-confidence clarification questions for developers (TDD §7).

    TODO(team): surface questions where extractor confidence < threshold;
    verified answers become permanent RKB knowledge.
    """
    orch = Orchestrator()
    return {"repository_id": repository_id, "questions": orch.pending_clarifications(repository_id)}
