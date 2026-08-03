"""Steps 3-6 (PRD): structure map, deep sub-agent analysis, findings.

Routes:
  POST /analysis/{repository_id}  — enqueue analysis as a FastAPI BackgroundTask;
                                    returns immediately with status=queued.
  GET  /analysis/{repository_id}  — read persisted findings from RKB (no re-run).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks

from imperium.api.schemas import AnalysisResponse
from imperium.core.orchestrator import Orchestrator

router = APIRouter(tags=["analysis"])

log = logging.getLogger("imperium.api.analysis")


def _run_analysis_background(repository_id: str) -> None:
    """Background task: run the full analysis pipeline and persist results."""
    try:
        orch = Orchestrator()
        orch.analyze(repository_id)
        log.info("Background analysis complete for %s", repository_id)
    except Exception as exc:  # noqa: BLE001
        log.error("Background analysis failed for %s: %s", repository_id, exc)


@router.post("/analysis/{repository_id}", response_model=AnalysisResponse)
def run_analysis(repository_id: str, background_tasks: BackgroundTasks) -> AnalysisResponse:
    """Enqueue the sub-agent analysis pipeline as a background task.

    Returns immediately with status=queued. Poll GET /analysis/{repository_id}
    to retrieve results once the pipeline completes.
    """
    background_tasks.add_task(_run_analysis_background, repository_id)
    return AnalysisResponse(repository_id=repository_id, status="queued")


@router.get("/analysis/{repository_id}", response_model=AnalysisResponse)
def get_analysis(repository_id: str) -> AnalysisResponse:
    """Fetch the latest analysis result from RKB (no re-run)."""
    orch = Orchestrator()
    return orch.get_analysis(repository_id)
