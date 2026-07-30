"""Claude-Code-style coding endpoint.

POST /api/code/{repository_id} with a natural-language instruction. The CodeAgent
locates the relevant code and edits it on an isolated branch, returning a summary +
unified diff for review. Never touches the default branch.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from imperium.agents.base import AgentContext
from imperium.agents.code_agent import CodeAgent

router = APIRouter(tags=["code"])


class CodeRequest(BaseModel):
    instruction: str
    repo_path: str = ""


@router.post("/code/{repository_id}")
def code_task(repository_id: str, req: CodeRequest) -> dict:
    """Run a coding task and return {applied, summary, branch, files_changed, diff}."""
    repo_path = req.repo_path
    if not repo_path:
        # resolve the workspace clone path from settings
        import os

        from imperium.config import get_settings

        repo_path = os.path.join(get_settings().workspace_dir, repository_id)

    ctx = AgentContext(repository_id=repository_id, repo_path=repo_path)
    from imperium.core.healing import heal_call

    return heal_call(
        "api.code",
        CodeAgent().run_task,
        ctx,
        req.instruction,
        default={"applied": False, "summary": "coding task failed", "diff": ""},
    )
