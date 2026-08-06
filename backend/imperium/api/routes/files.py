"""Workspace file browsing (VS Code Explorer + editor).

Serves the on-disk clone of an ingested repository so the IDE can render a file
tree and open files in the Monaco editor. Everything is owner-scoped through
``require_owner`` and hardened against path traversal — a caller can only read
files that resolve *inside* that repository's workspace directory.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Query, Request

from imperium.api.ownership import require_owner
from imperium.config import get_settings

log = logging.getLogger("imperium.api.files")
router = APIRouter(tags=["files"])

# Directories/files that are noise in a code browser — skip them in the tree.
_IGNORE = {
    ".git", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".venv", "venv", "dist", "build", ".next", ".turbo",
    ".idea", ".vscode", ".DS_Store", "coverage", ".egg-info",
}
_MAX_BYTES = 2_000_000  # refuse to stream anything larger than ~2MB into the editor


def _workspace(repository_id: str) -> str:
    """Absolute, real path to a repository's workspace root (must exist)."""
    root = os.path.realpath(os.path.join(get_settings().workspace_dir, repository_id))
    if not os.path.isdir(root):
        raise HTTPException(status_code=404, detail="Workspace not found (repo not cloned)")
    return root


def _safe_join(root: str, rel: str) -> str:
    """Join ``rel`` under ``root``, rejecting escapes (`..`, absolute, symlinks out)."""
    target = os.path.realpath(os.path.join(root, rel))
    if target != root and not target.startswith(root + os.sep):
        raise HTTPException(status_code=400, detail="Path escapes workspace")
    return target


def _build_tree(root: str, rel: str = "") -> list[dict]:
    """Recursive directory listing → nested {name, path, type, children?} nodes."""
    abs_dir = os.path.join(root, rel)
    try:
        entries = sorted(
            os.scandir(abs_dir),
            key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()),
        )
    except OSError:
        return []
    nodes: list[dict] = []
    for e in entries:
        if e.name in _IGNORE or e.name.endswith(".egg-info"):
            continue
        child_rel = os.path.join(rel, e.name) if rel else e.name
        if e.is_dir(follow_symlinks=False):
            nodes.append({
                "name": e.name,
                "path": child_rel,
                "type": "dir",
                "children": _build_tree(root, child_rel),
            })
        else:
            nodes.append({"name": e.name, "path": child_rel, "type": "file"})
    return nodes


@router.get("/files/{repository_id}/tree")
def file_tree(repository_id: str, request: Request) -> dict:
    """Return the repository's workspace as a nested file tree."""
    require_owner(repository_id, request)
    root = _workspace(repository_id)
    return {"repository_id": repository_id, "root": os.path.basename(root), "tree": _build_tree(root)}


@router.get("/files/{repository_id}/content")
def file_content(repository_id: str, request: Request, path: str = Query(...)) -> dict:
    """Return the UTF-8 text content of a single file inside the workspace."""
    require_owner(repository_id, request)
    root = _workspace(repository_id)
    target = _safe_join(root, path)
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="File not found")
    size = os.path.getsize(target)
    if size > _MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large ({size} bytes)")
    try:
        with open(target, "r", encoding="utf-8") as fh:
            content = fh.read()
        binary = False
    except (UnicodeDecodeError, ValueError):
        content = ""
        binary = True
    return {"path": path, "size": size, "binary": binary, "content": content}
