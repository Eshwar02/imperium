"""Liveness + backing-service readiness (TDD §10)."""
from __future__ import annotations

from fastapi import APIRouter

from imperium.rkb import cache, embeddings, graph, store

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/services")
def health_services() -> dict[str, dict[str, str]]:
    """Ping each backing store. Foundation: each client returns its status stub."""
    return {
        "postgres": store.ping(),
        "qdrant": embeddings.ping(),
        "neo4j": graph.ping(),
        "redis": cache.ping(),
    }
