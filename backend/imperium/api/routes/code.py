"""Claude-Code-style coding endpoints.

POST /api/code/{repository_id}          — run a coding task; returns summary + diff.
POST /api/code/{repository_id}/plan     — produce a multi-file refactor plan (no edits).
POST /api/code/{repository_id}/stream   — stream the agent's tool-calls live (SSE).

The CodeAgent locates the relevant code and edits it on an isolated branch, returning a
summary + unified diff for review. It never touches the default branch. With a
``test_command`` it also runs tests after editing and iterates on failures.
"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from imperium.agents.base import AgentContext
from imperium.agents.code_agent import CodeAgent
from imperium.api.ownership import require_owner

router = APIRouter(tags=["code"])


class CodeRequest(BaseModel):
    instruction: str
    repo_path: str = ""
    plan: bool = True
    test_command: str | None = None
    max_test_iters: int = 2
    steps: list[dict] | None = None  # optional pre-computed plan steps (for /graph)


def _resolve_repo_path(repository_id: str, repo_path: str) -> str:
    """Use an explicit path, else the workspace clone path from settings."""
    if repo_path:
        return repo_path
    from imperium.config import get_settings

    return os.path.join(get_settings().workspace_dir, repository_id)


def _ctx(repository_id: str, req: CodeRequest) -> AgentContext:
    return AgentContext(
        repository_id=repository_id,
        repo_path=_resolve_repo_path(repository_id, req.repo_path),
    )


@router.post("/code/{repository_id}")
def code_task(repository_id: str, req: CodeRequest, request: Request) -> dict:
    """Run a coding task and return {applied, summary, branch, files_changed, diff, plan, tests}."""
    require_owner(repository_id, request)
    from imperium.core.healing import heal_call

    return heal_call(
        "api.code",
        CodeAgent().run_task,
        _ctx(repository_id, req),
        req.instruction,
        default={"applied": False, "summary": "coding task failed", "diff": ""},
        plan=req.plan,
        test_command=req.test_command,
        max_test_iters=req.max_test_iters,
    )


@router.post("/code/{repository_id}/plan")
def code_plan(repository_id: str, req: CodeRequest, request: Request) -> dict:
    """Produce a multi-file refactor plan (no edits): {steps: [{file, action, rationale}], summary}."""
    require_owner(repository_id, request)
    from imperium.core.healing import heal_call

    return heal_call(
        "api.code.plan",
        CodeAgent().plan_task,
        _ctx(repository_id, req),
        req.instruction,
        default={"steps": [], "summary": "planning failed"},
    )


@router.post("/code/{repository_id}/graph")
def code_graph(repository_id: str, req: CodeRequest, request: Request) -> dict:
    """Lay out the task as a node graph via the small ``graph`` agent (dashed dep edges).

    Uses ``req.steps`` if provided; otherwise plans first. Returns ``{nodes, edges}``.
    """
    require_owner(repository_id, request)
    from imperium.agents.graph_agent import GraphAgent
    from imperium.core.healing import heal_call

    def _run():
        steps = req.steps
        if steps is None:
            steps = CodeAgent().plan_task(_ctx(repository_id, req), req.instruction).get("steps", [])
        return GraphAgent().layout(steps)

    return heal_call("api.code.graph", _run, default={"nodes": [], "edges": []})


@router.post("/code/{repository_id}/stream")
def code_stream(repository_id: str, req: CodeRequest, request: Request) -> StreamingResponse:
    """Stream the agent's plan, tool-calls, tests, and final diff as Server-Sent Events."""
    require_owner(repository_id, request)
    ctx = _ctx(repository_id, req)

    def gen():
        try:
            for ev in CodeAgent().stream_task(
                ctx,
                req.instruction,
                plan=req.plan,
                test_command=req.test_command,
                max_test_iters=req.max_test_iters,
            ):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as exc:  # noqa: BLE001 — never break the SSE stream
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
