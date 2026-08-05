"""Durable run lifecycle + live event stream (TDD §7/§8, Phase 3).

A *run* is the checkpointed LangGraph execution of the gated pipeline. Runs are
long-lived, resumable across the human gates, and stream progress over SSE — so the
premium IDE frontend can attach, watch agents work, and approve gates in place.

Routes:
  POST   /api/runs                    → start a run (drives to the first gate in the bg)
  GET    /api/runs                    → list runs (status / stage / gate; no event log)
  GET    /api/runs/{run_id}           → status / stage / progress / pending gate
  GET    /api/runs/{run_id}/graph     → live agent node graph ({nodes, edges}, §7b)
  POST   /api/runs/{run_id}/resume    → submit gate votes; resume to the next stop
  GET    /api/runs/{run_id}/events    → SSE stream of run events
  DELETE /api/runs/{run_id}           → delete a run (its live graph is deletable)
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from imperium.api.auth import get_user_id
from imperium.api.ownership import require_owner
from imperium.core.runs import run_manager

router = APIRouter(tags=["runs"])


def _guard_run(run_id: str, request: Request) -> None:
    """404 if the run is unknown, or provably owned by a different user.

    Mirrors ownership.require_owner: unclaimed runs (owner None) and no-user
    contexts (e.g. tests) stay accessible; only cross-user access is denied.
    """
    try:
        owner = run_manager.owner_of(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")
    uid = get_user_id(request)
    if owner is not None and uid is not None and owner != uid:
        raise HTTPException(status_code=404, detail="run not found")


class StartRunRequest(BaseModel):
    repository_id: str
    repo_path: str = ""


class ResumeRequest(BaseModel):
    votes: dict[str, str]  # {category: approve|reject|defer}


@router.post("/runs")
def start_run(req: StartRunRequest, background: BackgroundTasks, request: Request) -> dict:
    """Register a run and drive it to the first gate in the background."""
    require_owner(req.repository_id, request)
    run_id = run_manager.register(owner_id=get_user_id(request), repository_id=req.repository_id)
    background.add_task(run_manager.begin, run_id, req.repository_id, req.repo_path)
    return {"run_id": run_id, "status": "running"}


@router.get("/runs")
def list_runs(request: Request) -> dict:
    """List the caller's runs (status / stage / pending gate), newest fields only."""
    return {"runs": run_manager.list_runs(owner_id=get_user_id(request))}


@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request) -> dict:
    _guard_run(run_id, request)
    try:
        return run_manager.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")


@router.get("/runs/{run_id}/graph")
def get_run_graph(run_id: str, request: Request) -> dict:
    """The run's live execution as a node graph: {run_id, status, stage, nodes, edges}."""
    _guard_run(run_id, request)
    try:
        return run_manager.agent_graph(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")


@router.delete("/runs/{run_id}")
def delete_run(run_id: str, request: Request) -> dict:
    """Delete a run and its live graph."""
    _guard_run(run_id, request)
    try:
        run_manager.delete(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, "status": "deleted"}


@router.post("/runs/{run_id}/resume")
def resume_run(run_id: str, req: ResumeRequest, background: BackgroundTasks, request: Request) -> dict:
    _guard_run(run_id, request)
    try:
        run_manager.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")
    background.add_task(run_manager.resume_gate, run_id, req.votes)
    return {"run_id": run_id, "status": "resuming"}


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request) -> StreamingResponse:
    """Server-sent events: replays existing events then tails new ones until complete."""
    _guard_run(run_id, request)
    try:
        run_manager.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")

    async def event_stream():
        sent = 0
        while True:
            events = run_manager.get_events(run_id)
            for event in events[sent:]:
                yield f"data: {json.dumps(event)}\n\n"
            sent = len(events)
            status = run_manager.get_run(run_id)["status"]
            if status in ("complete", "failed"):
                yield f"data: {json.dumps({'event': status})}\n\n"
                return
            await asyncio.sleep(1.0)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
