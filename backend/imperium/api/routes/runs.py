"""Durable run lifecycle + live event stream (TDD §7/§8, Phase 3).

A *run* is the checkpointed LangGraph execution of the gated pipeline. Runs are
long-lived, resumable across the human gates, and stream progress over SSE — so the
premium IDE frontend can attach, watch agents work, and approve gates in place.

Routes:
  POST /api/runs                      → start a run (drives to the first gate in the bg)
  GET  /api/runs/{run_id}             → status / stage / progress / pending gate
  POST /api/runs/{run_id}/resume      → submit gate votes; resume to the next stop
  GET  /api/runs/{run_id}/events      → SSE stream of run events
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from imperium.core.runs import run_manager

router = APIRouter(tags=["runs"])


class StartRunRequest(BaseModel):
    repository_id: str
    repo_path: str = ""


class ResumeRequest(BaseModel):
    votes: dict[str, str]  # {category: approve|reject|defer}


@router.post("/runs")
def start_run(req: StartRunRequest, background: BackgroundTasks) -> dict:
    """Register a run and drive it to the first gate in the background."""
    run_id = run_manager.register()
    background.add_task(run_manager.begin, run_id, req.repository_id, req.repo_path)
    return {"run_id": run_id, "status": "running"}


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    try:
        return run_manager.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")


@router.post("/runs/{run_id}/resume")
def resume_run(run_id: str, req: ResumeRequest, background: BackgroundTasks) -> dict:
    try:
        run_manager.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")
    background.add_task(run_manager.resume_gate, run_id, req.votes)
    return {"run_id": run_id, "status": "resuming"}


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str) -> StreamingResponse:
    """Server-sent events: replays existing events then tails new ones until complete."""
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
