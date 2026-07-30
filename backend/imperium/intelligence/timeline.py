"""Repository Timeline — derive why the org codebase evolved (§1.6).

Parses git log to extract:
  - Commit-level churn (lines added/removed)
  - Authorship per file
  - Refactor signals (large renames, rewrites)
  - Dependency-shift signals (manifest changes)
  - Incident-driven changes (keywords in commit message)
  - Feature vs maintenance classification

Persists TimelineEvent rows to Postgres and embeds summaries in Qdrant.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger("imperium.intelligence.timeline")

# Commit message patterns for event classification
_INCIDENT_RE = re.compile(
    r"\b(hotfix|incident|bug|fix|revert|rollback|emergency|critical|sev[0-3])\b",
    re.IGNORECASE,
)
_REFACTOR_RE = re.compile(
    r"\b(refactor|restructure|cleanup|rewrite|rename|extract|split|decouple)\b",
    re.IGNORECASE,
)
_DEP_CHANGE_RE = re.compile(
    r"(requirements|package\.json|Pipfile|pyproject|pom\.xml|build\.gradle|yarn\.lock)",
    re.IGNORECASE,
)
_TEST_RE = re.compile(r"\b(test|spec|fixture|mock|stub)\b", re.IGNORECASE)
_DOC_RE = re.compile(r"\b(doc|readme|changelog|docs|comment)\b", re.IGNORECASE)

_MANIFEST_FILES = frozenset({
    "requirements.txt", "requirements-dev.txt", "Pipfile", "Pipfile.lock",
    "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "package-lock.json", "yarn.lock",
    "pom.xml", "build.gradle", "go.mod", "Cargo.toml",
})


@dataclass
class TimelineEntry:
    commit_sha: str
    author: str
    committed_at: dt.datetime
    message: str
    event_type: str
    files_changed: list[dict]       # [{path, insertions, deletions}]
    modules_affected: list[str]
    summary: str
    churn_lines: int
    extra: dict = field(default_factory=dict)


def _classify_event(message: str, files: list[dict]) -> str:
    """Classify a commit as one of: feature | refactor | incident_fix | dependency_shift | test | doc | churn."""
    file_names = [f.get("path", "") for f in files]
    if any(f in _MANIFEST_FILES or _DEP_CHANGE_RE.search(f) for f in file_names):
        return "dependency_shift"
    if _INCIDENT_RE.search(message):
        return "incident_fix"
    if _REFACTOR_RE.search(message):
        return "refactor"
    if _TEST_RE.search(message):
        return "test"
    if _DOC_RE.search(message):
        return "doc"
    churn = sum(f.get("insertions", 0) + f.get("deletions", 0) for f in files)
    if churn > 300:
        return "churn"
    return "feature"


def _summarize_commit(message: str, event_type: str, files: list[dict]) -> str:
    first_line = message.split("\n")[0][:150]
    n = len(files)
    churn = sum(f.get("insertions", 0) + f.get("deletions", 0) for f in files)
    return f"[{event_type}] {first_line} ({n} files, {churn} lines changed)"


def _extract_modules(files: list[dict]) -> list[str]:
    """Derive module/domain names from file paths (top-level directory)."""
    modules: set[str] = set()
    for f in files:
        parts = f.get("path", "").split("/")
        if len(parts) > 1:
            modules.add(parts[0])
        elif parts:
            modules.add(parts[0])
    return sorted(modules)


def parse_git_timeline(repo_path: str, max_commits: int = 2000) -> list[TimelineEntry]:
    """Walk git log and return structured TimelineEntry objects."""
    try:
        from git import InvalidGitRepositoryError, Repo
    except ImportError:
        log.warning("gitpython not installed — timeline unavailable")
        return []

    try:
        repo = Repo(repo_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("Cannot open repo at %s: %s", repo_path, exc)
        return []

    entries: list[TimelineEntry] = []

    for commit in repo.iter_commits(max_count=max_commits):
        try:
            # Diff stats
            files: list[dict] = []
            if commit.parents:
                diff = commit.diff(commit.parents[0], create_patch=False)
                stats = commit.stats.files
                for path, stat in stats.items():
                    files.append({
                        "path": path,
                        "insertions": stat.get("insertions", 0),
                        "deletions": stat.get("deletions", 0),
                        "lines": stat.get("lines", 0),
                    })
            else:
                # Root commit — no parent
                stats = commit.stats.files
                for path, stat in stats.items():
                    files.append({
                        "path": path,
                        "insertions": stat.get("insertions", 0),
                        "deletions": stat.get("deletions", 0),
                        "lines": stat.get("lines", 0),
                    })

            churn = sum(f["insertions"] + f["deletions"] for f in files)
            event_type = _classify_event(commit.message, files)
            modules = _extract_modules(files)
            summary = _summarize_commit(commit.message, event_type, files)
            committed_at = dt.datetime.fromtimestamp(commit.committed_date, tz=dt.timezone.utc).replace(tzinfo=None)

            entries.append(TimelineEntry(
                commit_sha=commit.hexsha,
                author=f"{commit.author.name} <{commit.author.email}>",
                committed_at=committed_at,
                message=commit.message[:500],
                event_type=event_type,
                files_changed=files,
                modules_affected=modules,
                summary=summary,
                churn_lines=churn,
            ))
        except Exception as exc:  # noqa: BLE001
            log.debug("Skipping commit %s: %s", commit.hexsha[:8], exc)
            continue

    log.info("Parsed %d timeline events from %s", len(entries), repo_path)
    return entries


def persist_timeline(repository_id: str, entries: list[TimelineEntry]) -> None:
    """Persist all timeline events to Postgres (idempotent by commit SHA)."""
    from imperium.rkb.store import get_session, upsert_timeline_event

    session = get_session()
    try:
        for e in entries:
            upsert_timeline_event(
                session=session,
                repository_id=repository_id,
                commit_sha=e.commit_sha,
                author=e.author,
                committed_at=e.committed_at,
                event_type=e.event_type,
                files_changed=e.files_changed,
                modules_affected=e.modules_affected,
                summary=e.summary,
                churn_lines=e.churn_lines,
            )
    finally:
        session.close()
    log.info("Persisted %d timeline events for repo %s", len(entries), repository_id)


def embed_timeline_summaries(repository_id: str, entries: list[TimelineEntry]) -> None:
    """Store timeline summaries as Qdrant vectors for narrative agent context."""
    from imperium.rkb.embeddings import upsert

    texts = [e.summary for e in entries]
    payloads = [
        {
            "repository_id": repository_id,
            "level": "timeline",
            "commit_sha": e.commit_sha,
            "event_type": e.event_type,
            "author": e.author,
            "committed_at": e.committed_at.isoformat() if e.committed_at else None,
        }
        for e in entries
    ]
    if texts:
        upsert(texts, payloads)


def build_timeline(repository_id: str, repo_path: str, embed: bool = True) -> list[TimelineEntry]:
    """Full pipeline: parse → persist → embed."""
    entries = parse_git_timeline(repo_path)
    persist_timeline(repository_id, entries)
    if embed:
        embed_timeline_summaries(repository_id, entries)
    return entries


def get_churn_summary(repository_id: str) -> dict:
    """Return per-file churn totals from Postgres for priority scoring."""
    from imperium.rkb.store import get_session, get_timeline

    session = get_session()
    try:
        events = get_timeline(session, repository_id)
    finally:
        session.close()

    churn: dict[str, int] = {}
    for event in events:
        for f in event.files_changed:
            if isinstance(f, str):
                churn[f] = churn.get(f, 0) + 1
            elif isinstance(f, dict):
                p = f.get("path", "")
                churn[p] = churn.get(p, 0) + f.get("lines", 0)
    return churn
