"""API Mapper (TDD §4). Catalogues exposed + consumed API contracts (PRD Step 2).

Detects, per source file:
  - **Exposed** HTTP routes — FastAPI/Flask/Django-style decorators
    (``@app.get("/x")``, ``@router.post(...)``, ``@app.route("/x", methods=[...])``).
  - **Consumed** HTTP calls — ``requests``/``httpx``/``urllib`` and ``fetch``/``axios``
    with an inferable method + URL/path.

Pragmatic regex detection (Python/JS-first) that degrades gracefully — an enterprise
codebase is scanned file-by-file so a weird file never fails the whole map. Feeds the
**API graph** layer (EXPOSES / CONSUMES edges) in Neo4j.
"""
from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("imperium.intelligence.api_mapper")

_SOURCE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java"}
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".mypy_cache"}
_MAX_FILE_BYTES = 400_000

# @app.get("/path")  /  @router.post('/path')  /  @blueprint.route("/path")
_DECORATOR_ROUTE = re.compile(
    r"@\w+\.(get|post|put|patch|delete|route)\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
# methods=["GET","POST"] on Flask/Django @route
_METHODS_KW = re.compile(r"methods\s*=\s*\[([^\]]*)\]", re.IGNORECASE)

# requests.get("http://..") / httpx.post('/api/x') / client.delete(url)
_CONSUMED_CALL = re.compile(
    r"(?:requests|httpx|client|session|urllib\.request)\.(get|post|put|patch|delete)\(\s*(?:f?['\"]([^'\"]*)['\"])?",
    re.IGNORECASE,
)
# JS: fetch("/api/x", {method:"POST"}) / axios.get("/x")
_FETCH_CALL = re.compile(r"\bfetch\(\s*[`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)
_AXIOS_CALL = re.compile(r"\baxios\.(get|post|put|patch|delete)\(\s*[`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)


def _iter_files(repo_path: str):
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() in _SOURCE_EXTS:
                yield os.path.join(root, name)


def _read(path: str) -> list[str] | None:
    try:
        if os.path.getsize(path) > _MAX_FILE_BYTES:
            return None
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return None


def map_apis(repo_path: str) -> list[dict]:
    """Return API records: [{kind: exposed|consumed, method, path, call_sites}].

    ``call_sites`` are ``file:line`` strings; identical (kind, method, path) records are
    merged across files with their sites accumulated.
    """
    records: dict[tuple[str, str, str], dict] = {}

    def _add(kind: str, method: str, path: str, site: str) -> None:
        key = (kind, method.upper(), path)
        rec = records.setdefault(
            key, {"kind": kind, "method": method.upper(), "path": path, "call_sites": []}
        )
        if site not in rec["call_sites"]:
            rec["call_sites"].append(site)

    for fpath in _iter_files(repo_path):
        lines = _read(fpath)
        if lines is None:
            continue
        rel = os.path.relpath(fpath, repo_path)
        for i, line in enumerate(lines, 1):
            site = f"{rel}:{i}"

            m = _DECORATOR_ROUTE.search(line)
            if m:
                verb, path = m.group(1), m.group(2)
                if verb.lower() == "route":
                    methods = _METHODS_KW.search(line)
                    verbs = (
                        [v.strip(" '\"").upper() for v in methods.group(1).split(",") if v.strip()]
                        if methods
                        else ["GET"]
                    )
                    for v in verbs:
                        _add("exposed", v, path, site)
                else:
                    _add("exposed", verb, path, site)

            for cm in _CONSUMED_CALL.finditer(line):
                _add("consumed", cm.group(1), cm.group(2) or "<dynamic>", site)
            for fm in _FETCH_CALL.finditer(line):
                _add("consumed", "GET", fm.group(1), site)
            for am in _AXIOS_CALL.finditer(line):
                _add("consumed", am.group(1), am.group(2), site)

    result = list(records.values())
    log.info("Mapped %d API records from %s", len(result), repo_path)
    return result
