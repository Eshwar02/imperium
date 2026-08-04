"""Database Mapper (TDD §4). Extracts schema + data-access paths.

Detects:
  - **Tables** — SQLAlchemy ``__tablename__ = "x"`` and Django ``class X(models.Model)``.
  - **Access** — raw SQL statements (``SELECT/INSERT/UPDATE/DELETE ... FROM/INTO table``)
    with their operation + call site.

Pragmatic regex detection that degrades gracefully per file. Feeds the **data graph**
layer (READS / WRITES edges between code and tables) in Neo4j and the data-flow tests.
"""
from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("imperium.intelligence.db_mapper")

_SOURCE_EXTS = {".py", ".js", ".ts", ".sql", ".rb", ".java", ".go"}
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".mypy_cache"}
_MAX_FILE_BYTES = 400_000

_TABLENAME = re.compile(r"__tablename__\s*=\s*['\"]([A-Za-z_][\w]*)['\"]")
_DJANGO_MODEL = re.compile(r"class\s+(\w+)\s*\(\s*models\.Model\s*\)")
_SQL_READ = re.compile(r"\bSELECT\b.+?\bFROM\s+([A-Za-z_][\w\.]*)", re.IGNORECASE | re.DOTALL)
_SQL_WRITE = re.compile(
    r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([A-Za-z_][\w\.]*)", re.IGNORECASE
)


def _iter_files(repo_path: str):
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() in _SOURCE_EXTS:
                yield os.path.join(root, name)


def _read(path: str) -> str | None:
    try:
        if os.path.getsize(path) > _MAX_FILE_BYTES:
            return None
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def map_database(repo_path: str) -> dict:
    """Return {tables: [{name, source}], access: [{table, op, location}]}."""
    tables: dict[str, str] = {}
    access: list[dict] = []

    def _add_table(name: str, site: str) -> None:
        tables.setdefault(name, site)

    def _add_access(table: str, op: str, site: str) -> None:
        table = table.split(".")[-1]  # strip schema qualifier
        access.append({"table": table, "op": op, "location": site})

    for fpath in _iter_files(repo_path):
        text = _read(fpath)
        if text is None:
            continue
        rel = os.path.relpath(fpath, repo_path)

        for m in _TABLENAME.finditer(text):
            _add_table(m.group(1), f"{rel}:{_line_of(text, m.start())}")
        for m in _DJANGO_MODEL.finditer(text):
            _add_table(m.group(1).lower(), f"{rel}:{_line_of(text, m.start())}")
        for m in _SQL_READ.finditer(text):
            _add_access(m.group(1), "read", f"{rel}:{_line_of(text, m.start())}")
        for m in _SQL_WRITE.finditer(text):
            _add_access(m.group(2), "write", f"{rel}:{_line_of(text, m.start())}")

    result = {
        "tables": [{"name": n, "source": s} for n, s in tables.items()],
        "access": access,
    }
    log.info("Mapped %d tables, %d access sites from %s", len(tables), len(access), repo_path)
    return result
