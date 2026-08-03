"""Database Mapper (TDD §4). Extracts schema + data access paths.

Detects ORM models (SQLAlchemy, Django ORM, Hibernate), migration files, and raw SQL;
builds a table+column inventory and read/write access map per code location.

Strategy:
  1. SQLAlchemy — scan for class declarations inheriting DeclarativeBase/Base with
     __tablename__ and mapped_column/Column attributes.
  2. Django ORM — scan for models.Model subclasses with Field declarations.
  3. Raw SQL — regex scan for SELECT/INSERT/UPDATE/DELETE/CREATE TABLE statements.
  4. Migration files — detect alembic versions/, Django migrations/, Flyway *.sql.
"""
from __future__ import annotations

import ast
import logging
import os
import re
from dataclasses import dataclass, field

log = logging.getLogger("imperium.intelligence.db_mapper")

# SQL operation patterns
_SQL_RE = re.compile(
    r"\b(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE|DROP\s+TABLE|ALTER\s+TABLE)\b"
    r"(?:\s+\w+)?\s+(?:FROM\s+|INTO\s+|TABLE\s+)?([`\"\[]?[\w.]+[`\"\]]?)?",
    re.IGNORECASE | re.DOTALL,
)

_MIGRATION_DIRS = frozenset({"migrations", "alembic", "flyway", "liquibase", "db/migrate"})
_SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build"}


@dataclass
class TableInfo:
    name: str
    columns: list[dict] = field(default_factory=list)   # [{name, type}]
    source_file: str = ""
    orm: str = ""   # sqlalchemy | django | raw | migration


@dataclass
class AccessEntry:
    table: str
    op: str         # SELECT | INSERT | UPDATE | DELETE | CREATE | DROP | ALTER
    location: str   # file:line


def _scan_sqlalchemy(source: str, file_path: str) -> list[TableInfo]:
    """Detect SQLAlchemy ORM model classes and their columns."""
    tables: list[TableInfo] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return tables

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check for __tablename__ attribute
        tablename = None
        columns: list[dict] = []

        for item in node.body:
            # __tablename__ = "foo"
            if (
                isinstance(item, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "__tablename__"
                    for t in item.targets
                )
                and isinstance(item.value, ast.Constant)
            ):
                tablename = str(item.value.value)

            # col: Mapped[str] = mapped_column(String) OR col = Column(String)
            if isinstance(item, (ast.Assign, ast.AnnAssign)):
                col_name = None
                col_type = "unknown"
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    col_name = item.target.id
                elif isinstance(item, ast.Assign):
                    for t in item.targets:
                        if isinstance(t, ast.Name):
                            col_name = t.id
                            break

                # Extract type from mapped_column(String) or Column(String)
                val = item.value if isinstance(item, ast.Assign) else item.value
                if isinstance(val, ast.Call) and isinstance(val.func, (ast.Name, ast.Attribute)):
                    func_name = (
                        val.func.id
                        if isinstance(val.func, ast.Name)
                        else val.func.attr
                    )
                    if func_name in ("mapped_column", "Column", "relationship"):
                        if val.args and isinstance(val.args[0], (ast.Name, ast.Attribute)):
                            col_type = (
                                val.args[0].id
                                if isinstance(val.args[0], ast.Name)
                                else val.args[0].attr
                            )

                if col_name and not col_name.startswith("_") and col_name != "__tablename__":
                    columns.append({"name": col_name, "type": col_type})

        if tablename:
            tables.append(TableInfo(
                name=tablename,
                columns=columns,
                source_file=file_path,
                orm="sqlalchemy",
            ))

    return tables


def _scan_django(source: str, file_path: str) -> list[TableInfo]:
    """Detect Django ORM model classes."""
    tables: list[TableInfo] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return tables

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check inheritance for models.Model
        is_model = any(
            (isinstance(b, ast.Attribute) and b.attr == "Model") or
            (isinstance(b, ast.Name) and b.id == "Model")
            for b in node.bases
        )
        if not is_model:
            continue

        # Table name is snake_case of class name by default
        tablename = re.sub(r"(?<!^)(?=[A-Z])", "_", node.name).lower()
        columns: list[dict] = []

        for item in node.body:
            if isinstance(item, ast.Assign):
                for t in item.targets:
                    if isinstance(t, ast.Name) and isinstance(item.value, ast.Call):
                        func = item.value.func
                        field_type = func.attr if isinstance(func, ast.Attribute) else (
                            func.id if isinstance(func, ast.Name) else "Field"
                        )
                        if "Field" in field_type or "Key" in field_type:
                            columns.append({"name": t.id, "type": field_type})

        tables.append(TableInfo(
            name=tablename,
            columns=columns,
            source_file=file_path,
            orm="django",
        ))

    return tables


def _scan_sql_access(source: str, file_path: str) -> list[AccessEntry]:
    """Regex scan for raw SQL statements in any file."""
    access: list[AccessEntry] = []
    lines = source.splitlines()
    for i, line in enumerate(lines, 1):
        for m in _SQL_RE.finditer(line):
            op = m.group(1).split()[0].upper()  # SELECT, INSERT, UPDATE, etc.
            table = (m.group(2) or "").strip("`\"[]").lower()
            if table:
                access.append(AccessEntry(
                    table=table,
                    op=op,
                    location=f"{file_path}:{i}",
                ))
    return access


def _is_migration_file(file_path: str) -> bool:
    parts = file_path.replace("\\", "/").split("/")
    return any(p in _MIGRATION_DIRS for p in parts)


def map_database(repo_path: str) -> dict:
    """Return {tables: [...], access: [{table, op, location}]}.

    tables: list of {name, columns, source_file, orm}
    access: list of {table, op, location}
    """
    tables: list[TableInfo] = []
    access: list[AccessEntry] = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            fp = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()

            try:
                with open(fp, encoding="utf-8", errors="ignore") as fh:
                    source = fh.read()
            except OSError:
                continue

            # Python — AST-based ORM detection + raw SQL
            if ext == ".py":
                tables.extend(_scan_sqlalchemy(source, fp))
                tables.extend(_scan_django(source, fp))
                access.extend(_scan_sql_access(source, fp))
                continue

            # SQL files — migrations and raw queries
            if ext in (".sql",):
                access.extend(_scan_sql_access(source, fp))
                # CREATE TABLE detection
                for m in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"\[]?[\w.]+[`\"\]]?)",
                                      source, re.IGNORECASE):
                    tname = m.group(1).strip("`\"[]").lower()
                    tables.append(TableInfo(name=tname, source_file=fp, orm="sql"))
                continue

            # Java/Kotlin — Hibernate @Entity / @Table
            if ext in (".java", ".kt"):
                for m in re.finditer(r'@Table\s*\(\s*name\s*=\s*["\']([^"\']+)["\']', source, re.IGNORECASE):
                    tables.append(TableInfo(name=m.group(1).lower(), source_file=fp, orm="hibernate"))
                access.extend(_scan_sql_access(source, fp))

    # Deduplicate tables by name
    seen_tables: set[str] = set()
    unique_tables: list[TableInfo] = []
    for t in tables:
        if t.name not in seen_tables:
            seen_tables.add(t.name)
            unique_tables.append(t)

    log.info(
        "DB mapper: %d tables, %d access entries in %s",
        len(unique_tables), len(access), repo_path,
    )

    return {
        "tables": [
            {
                "name": t.name,
                "columns": t.columns,
                "source_file": t.source_file,
                "orm": t.orm,
            }
            for t in unique_tables
        ],
        "access": [
            {"table": a.table, "op": a.op, "location": a.location}
            for a in access
        ],
    }
