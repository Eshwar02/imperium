"""DB2 (EXEC SQL) + CICS (EXEC CICS) edge extraction from COBOL source.

Kept separate from ``cobol.py`` so the SQL/CICS parsing has one clear home and can be
reused by a DDL frontend later. Emits ``{"source","target","type"}`` edge dicts:
  - READS(program → Db2Table)  for SELECT ... FROM / JOIN
  - WRITES(program → Db2Table) for INSERT INTO / UPDATE / DELETE FROM
  - EXPOSES(program → CicsTransaction) for EXEC CICS ... TRANSID('x')
"""
from __future__ import annotations

import re

_SQL_BLOCK_RE = re.compile(r"EXEC\s+SQL(.+?)END-EXEC", re.IGNORECASE | re.DOTALL)
_FROM_RE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Z][A-Z0-9_\.]*)", re.IGNORECASE)
_INSERT_RE = re.compile(r"\bINSERT\s+INTO\s+([A-Z][A-Z0-9_\.]*)", re.IGNORECASE)
_UPDATE_RE = re.compile(r"\bUPDATE\s+([A-Z][A-Z0-9_\.]*)", re.IGNORECASE)
_DELETE_RE = re.compile(r"\bDELETE\s+FROM\s+([A-Z][A-Z0-9_\.]*)", re.IGNORECASE)

_CICS_BLOCK_RE = re.compile(r"EXEC\s+CICS(.+?)END-EXEC", re.IGNORECASE | re.DOTALL)
_TRANSID_RE = re.compile(r"TRANSID\s*\(\s*'([^']+)'\s*\)", re.IGNORECASE)


def extract_sql_edges(program: str, src: str) -> list[dict]:
    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for block in _SQL_BLOCK_RE.finditer(src):
        body = block.group(1)
        writes = {m.group(1).upper() for rx in (_INSERT_RE, _UPDATE_RE, _DELETE_RE)
                  for m in rx.finditer(body)}
        for tbl in writes:
            key = ("WRITES", tbl)
            if key not in seen:
                seen.add(key)
                edges.append({"source": program, "target": tbl, "type": "WRITES"})
        for m in _FROM_RE.finditer(body):
            tbl = m.group(1).upper()
            if tbl in writes:  # UPDATE/DELETE ... where the table is the write target
                continue
            key = ("READS", tbl)
            if key not in seen:
                seen.add(key)
                edges.append({"source": program, "target": tbl, "type": "READS"})
    return edges


def extract_cics(program: str, src: str) -> list[dict]:
    edges: list[dict] = []
    seen: set[str] = set()
    for block in _CICS_BLOCK_RE.finditer(src):
        for m in _TRANSID_RE.finditer(block.group(1)):
            txn = m.group(1).upper()
            if txn not in seen:
                seen.add(txn)
                edges.append({"source": program, "target": txn, "type": "EXPOSES"})
    return edges
