"""Repository loader (PRD Step 1). Clone a git URL (or accept an upload) into an
isolated workspace under WORKSPACE_DIR. Persists a Repository row to RKB after clone.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass

from imperium.config import get_settings

log = logging.getLogger("imperium.ingestion.loader")


@dataclass
class LoadedRepo:
    id: str
    path: str
    url: str | None
    ref: str
    languages: list[str]


def load_repository(repo_url: str | None, ref: str = "HEAD") -> LoadedRepo:
    """Clone or accept a repository and persist a Repository row to Postgres."""
    settings = get_settings()
    repo_id = str(uuid.uuid4())
    workspace = os.path.join(settings.workspace_dir, repo_id)
    os.makedirs(workspace, exist_ok=True)

    if repo_url:
        try:
            from git import Repo

            log.info("Cloning %s (ref=%s) → %s", repo_url, ref, workspace)
            Repo.clone_from(repo_url, workspace)
            if ref != "HEAD":
                Repo(workspace).git.checkout(ref)
        except Exception as exc:  # noqa: BLE001
            log.warning("Clone failed for %s: %s", repo_url, exc)
    # else: uploaded archive — workspace already populated by upload handler

    # Detect languages
    languages: list[str] = []
    try:
        from imperium.intelligence import language_detection

        languages = language_detection.detect(workspace)
    except Exception as exc:  # noqa: BLE001
        log.warning("Language detection failed: %s", exc)

    # Persist Repository row to Postgres (idempotent upsert)
    try:
        from imperium.rkb.store import get_session, upsert_repository

        session = get_session()
        try:
            upsert_repository(session, repo_id, repo_url, ref, languages)
        finally:
            session.close()
        log.info("Persisted repository %s to RKB", repo_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not persist repository row: %s", exc)

    return LoadedRepo(id=repo_id, path=workspace, url=repo_url, ref=ref, languages=languages)
