"""Steps 3-6 (PRD): structure map, deep sub-agent analysis, findings."""
from __future__ import annotations

from fastapi import APIRouter

from imperium.api.schemas import AnalysisResponse
from imperium.core.orchestrator import Orchestrator

router = APIRouter(tags=["analysis"])


@router.post("/analysis/{repository_id}", response_model=AnalysisResponse)
def run_analysis(repository_id: str) -> AnalysisResponse:
    """Run the sub-agent analysis pipeline and return structure map + findings.

    TODO(team): make async (background task / queue); stream progress to UI.
    """
    orch = Orchestrator()
    result = orch.analyze(repository_id)
    return result


@router.get("/analysis/{repository_id}", response_model=AnalysisResponse)
def get_analysis(repository_id: str) -> AnalysisResponse:
    """Fetch the latest analysis result from RKB.

    TODO(team): read from RKB instead of re-running.
    """
    orch = Orchestrator()
    return orch.get_analysis(repository_id)
