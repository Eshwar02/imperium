"""Steps 3-6 (PRD): structure map, deep sub-agent analysis, findings."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from imperium.api.schemas import AnalysisResponse
from imperium.core.orchestrator import Orchestrator

router = APIRouter(tags=["analysis"])


@router.post("/analysis/{repository_id}", response_model=AnalysisResponse)
def run_analysis(repository_id: str, background_tasks: BackgroundTasks) -> AnalysisResponse:
    """Kick off the sub-agent analysis pipeline in the background.

    Returns immediately with status ``running``; poll GET /analysis/{id} for the
    result, or subscribe to the run's SSE stream for live progress.
    """
    orch = Orchestrator()
    background_tasks.add_task(orch.analyze_in_background, repository_id)
    return AnalysisResponse(repository_id=repository_id, status="running")


@router.get("/analysis/{repository_id}", response_model=AnalysisResponse)
def get_analysis(repository_id: str) -> AnalysisResponse:
    """Fetch the latest analysis result (cached snapshot, then RKB fallback)."""
    orch = Orchestrator()
    return orch.get_analysis(repository_id)
