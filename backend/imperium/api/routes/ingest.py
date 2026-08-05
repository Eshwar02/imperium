"""Step 1 Ingestion (TDD §3, PRD Step 1-2). Clone/upload repo, detect stack.

After loading, kicks off the knowledge-base pipeline (parse → graph → embed → priority).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Request

from imperium.api.auth import get_user_id
from imperium.api.schemas import IngestRequest, IngestResponse
from imperium.ingestion.loader import load_repository

log = logging.getLogger("imperium.api.ingest")
router = APIRouter(tags=["ingest"])


def _build_kb(repository_id: str, repo_path: str) -> None:
    """Background task: build the full knowledge base after ingestion."""
    try:
        from imperium.core.orchestrator import Orchestrator

        orch = Orchestrator()
        result = orch.build_knowledge_base(repository_id, repo_path)
        log.info("Knowledge base built for %s: %s", repository_id, result)
    except Exception as exc:  # noqa: BLE001
        log.warning("Knowledge base build failed for %s: %s", repository_id, exc)


@router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest, background_tasks: BackgroundTasks, request: Request) -> IngestResponse:
    """Load a repository into a workspace, persist to RKB, and kick off KB pipeline.

    The knowledge-base pipeline (parse → call graph → embeddings → priority → timeline)
    runs in the background so the response is immediate.
    """
    repo = load_repository(req.repo_url, ref=req.ref, owner_id=get_user_id(request))
    background_tasks.add_task(_build_kb, repo.id, repo.path)
    return IngestResponse(repository_id=repo.id, languages=repo.languages)
