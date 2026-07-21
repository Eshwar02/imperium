"""Shared API request/response models. Foundation: shapes the pipeline contract."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class IngestRequest(BaseModel):
    repo_url: str | None = None  # git URL; or upload via multipart
    ref: str = "HEAD"


class IngestResponse(BaseModel):
    repository_id: str
    languages: list[str] = []
    status: str = "ingested"


class AnalysisResponse(BaseModel):
    repository_id: str
    status: str  # queued | running | complete
    structure_map: dict | None = None       # nodes/edges for React Flow (TDD §3)
    findings: list["Finding"] = []


class Finding(BaseModel):
    category: "Category"
    title: str
    detail: str
    confidence: float = 0.0
    locations: list[str] = []


class Category(str, Enum):
    security = "security"
    performance = "performance"
    modernization = "modernization"
    integration = "integration"
    documentation = "documentation"


class GateDecision(str, Enum):
    approve = "approve"
    reject = "reject"
    defer = "defer"


class GateVote(BaseModel):
    category: Category
    decision: GateDecision
    note: str | None = None


class GateRequest(BaseModel):
    repository_id: str
    votes: list[GateVote]


AnalysisResponse.model_rebuild()
