"""Read APIs over the Repo Intelligence Engine (TDD §3-§6).

Thin, resilient GET endpoints the frontend consumes: graph layers, memory hierarchy,
business rules, priorities, changesets, simulations, timeline, and token usage. Each
degrades to an empty payload rather than erroring, so the UI never hits a dead route.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from imperium.api.ownership import require_owner
from imperium.core.healing import heal_call

log = logging.getLogger("imperium.api.insights")

router = APIRouter(tags=["insights"])

_LAYER_RELS = {
    "call": ["CALLS"],
    "dependency": ["DEPENDS_ON"],
    "api": ["EXPOSES", "CONSUMES"],
    "data": ["READS", "WRITES"],
    "arch": None,  # full graph
    "all": None,
}


def _session_query(fn, *args):
    """Open a session, run ``fn(session, *args)``, always close. Healed + safe."""

    def _run():
        from imperium.rkb.store import get_session

        session = get_session()
        try:
            return fn(session, *args)
        finally:
            session.close()

    return heal_call("api.insights", _run, default=[])


# ── graph ─────────────────────────────────────────────────────────────────────

@router.get("/graph/{repository_id}")
def get_graph(repository_id: str, request: Request, layer: str = "all") -> dict:
    """Return a graph layer ({nodes, edges}). layer: call|dependency|api|data|arch|all."""
    require_owner(repository_id, request)
    rels = _LAYER_RELS.get(layer, None)

    def _run():
        from imperium.rkb.graph import layer_graph

        return layer_graph(repository_id, rels)

    return heal_call("api.graph", _run, default={"nodes": [], "edges": []})


@router.get("/graph/{repository_id}/blast/{node_id}")
def get_blast_radius(
    repository_id: str, node_id: str, request: Request, depth: int = 3
) -> dict:
    require_owner(repository_id, request)

    def _run():
        from imperium.rkb.graph import blast_radius

        return {"node_id": node_id, "dependents": blast_radius(node_id, depth)}

    return heal_call("api.blast", _run, default={"node_id": node_id, "dependents": []})


# ── hierarchy + relational reads ──────────────────────────────────────────────

@router.get("/hierarchy/{repository_id}")
def get_hierarchy(repository_id: str, request: Request) -> dict:
    require_owner(repository_id, request)
    from imperium.rkb.store import get_modules

    modules = _session_query(get_modules, repository_id)
    return {
        "repository_id": repository_id,
        "modules": [
            {
                "name": getattr(m, "name", ""),
                "path": getattr(m, "path", ""),
                "summary": getattr(m, "summary", ""),
                "ai_authorship_pct": getattr(m, "ai_authorship_pct", 0.0),
                "flagged_for_review": getattr(m, "flagged_for_review", False),
            }
            for m in modules
        ],
    }


@router.get("/business-rules/{repository_id}")
def get_rules(repository_id: str, request: Request) -> dict:
    require_owner(repository_id, request)
    from imperium.rkb.store import get_business_rules

    rules = _session_query(get_business_rules, repository_id)
    return {
        "rules": [
            {
                "id": getattr(r, "id", ""),
                "statement": getattr(r, "statement", ""),
                "confidence": getattr(r, "confidence", 0.0),
                "verified": getattr(r, "verified", False),
                "locations": getattr(r, "locations", []),
            }
            for r in rules
        ]
    }


@router.get("/priorities/{repository_id}")
def get_priorities_route(repository_id: str, request: Request) -> dict:
    require_owner(repository_id, request)
    from imperium.rkb.store import get_priorities

    rows = _session_query(get_priorities, repository_id)
    return {
        "priorities": [
            {
                "score": getattr(p, "score", 0.0),
                "path": getattr(p, "path", getattr(p, "module_path", "")),
                "factors": getattr(p, "factors", {}),
            }
            for p in rows
        ]
    }


@router.get("/changesets/{repository_id}")
def get_changesets_route(repository_id: str, request: Request) -> dict:
    require_owner(repository_id, request)
    from imperium.rkb.store import get_changesets

    rows = _session_query(get_changesets, repository_id)
    return {
        "changesets": [
            {
                "id": getattr(c, "id", ""),
                "name": getattr(c, "name", ""),
                "status": getattr(c, "status", ""),
                "files": [getattr(f, "file_path", "") for f in getattr(c, "files", [])],
            }
            for c in rows
        ]
    }


@router.get("/simulations/{repository_id}")
def get_simulations_route(repository_id: str, request: Request) -> dict:
    require_owner(repository_id, request)
    from imperium.rkb.store import get_simulations

    rows = _session_query(get_simulations, repository_id)
    return {
        "simulations": [
            {
                "file_path": getattr(s, "file_path", ""),
                "confidence_score": getattr(s, "confidence_score", 0.0),
                "safety_passed": getattr(s, "safety_passed", False),
                "blocked": getattr(s, "blocked", False),
                "diff": getattr(s, "diff", ""),
            }
            for s in rows
        ]
    }


@router.get("/timeline/{repository_id}")
def get_timeline_route(repository_id: str, request: Request) -> dict:
    require_owner(repository_id, request)
    from imperium.rkb.store import get_timeline

    rows = _session_query(get_timeline, repository_id)
    return {
        "events": [
            {
                "commit_sha": getattr(e, "commit_sha", ""),
                "summary": getattr(e, "summary", ""),
                "author": getattr(e, "author", ""),
            }
            for e in rows
        ]
    }


@router.get("/usage")
def get_usage() -> dict:
    """Per-agent-role token accounting accumulated in-process (Phase 1)."""
    def _run():
        from imperium.llm.client import get_token_usage

        return get_token_usage()

    return {"usage": heal_call("api.usage", _run, default={})}
