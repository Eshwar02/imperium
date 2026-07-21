"""Step 1 Ingestion (TDD §3, PRD Step 1-2). Clone/upload repo, detect stack."""
from __future__ import annotations

from fastapi import APIRouter

from imperium.api.schemas import IngestRequest, IngestResponse
from imperium.ingestion.loader import load_repository
from imperium.intelligence import language_detection

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest) -> IngestResponse:
    """Load a repository into a workspace and detect languages.

    TODO(team): persist repository row in RKB, kick off async analysis.
    """
    repo = load_repository(req.repo_url, ref=req.ref)
    languages = language_detection.detect(repo.path)
    return IngestResponse(repository_id=repo.id, languages=languages)
