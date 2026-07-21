"""Repository loader (PRD Step 1). Clone a git URL (or accept an upload) into an
isolated workspace under WORKSPACE_DIR.

Foundation: real clone via GitPython + workspace layout. Upload path + RKB row are
TODO(team).
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from imperium.config import get_settings


@dataclass
class LoadedRepo:
    id: str
    path: str
    url: str | None
    ref: str


def load_repository(repo_url: str | None, ref: str = "HEAD") -> LoadedRepo:
    settings = get_settings()
    repo_id = str(uuid.uuid4())
    workspace = os.path.join(settings.workspace_dir, repo_id)
    os.makedirs(workspace, exist_ok=True)

    if repo_url:
        # Real clone. TODO(team): shallow clone, auth for private repos, size guard.
        from git import Repo

        Repo.clone_from(repo_url, workspace)
        if ref != "HEAD":
            Repo(workspace).git.checkout(ref)
    # else: TODO(team) — accept archive upload extracted into `workspace`.

    return LoadedRepo(id=repo_id, path=workspace, url=repo_url, ref=ref)
