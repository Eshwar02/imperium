"""Database Mapper (TDD §4). Extracts schema + data access paths.

TODO(team): detect ORM models / migrations / raw SQL, build table+column
inventory and read/write access map (feeds data-flow testing, PRD §10).
"""
from __future__ import annotations


def map_database(repo_path: str) -> dict:
    """Return {tables: [...], access: [{table, op, location}]}. TODO(team)."""
    raise NotImplementedError("database mapping — team task")
