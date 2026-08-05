"""COBOL frontend — column-aware regex spine (tree-sitter-cobol optional).

Turns COBOL programs into the shared ``AstNode`` shape: a ``module`` (program) whose
``function`` children are PROCEDURE-DIVISION paragraphs, each carrying ``call`` children
for ``PERFORM`` / ``CALL 'x'`` / ``GO TO`` targets — so the existing call-graph builder
resolves paragraph nodes and PERFORMS/CALLS edges unchanged. Also emits COPIES edges
(program → copybook), EXEC SQL READS/WRITES, EXEC CICS EXPOSES, and DATA-DIVISION items
(incl. 88-level condition names) for the business-rule extractor.
"""
from __future__ import annotations

import re

from imperium.intelligence.ast_builder import AstNode

# ── preprocessing ─────────────────────────────────────────────────────────────


def _detect_format(src: str) -> str:
    """"fixed" if the source uses the classic 80-col layout, else "free"."""
    for line in src.splitlines()[:200]:
        if len(line) >= 6 and line[:6].strip().isdigit():
            return "fixed"
        if len(line) >= 7 and line[6:7] in ("*", "/", "-") and line[:6].strip() == "":
            return "fixed"
    return "free"


def _strip_fixed(src: str) -> str:
    """Drop sequence area (1-6) + identification area (73-80); skip comment lines (col 7)."""
    out: list[str] = []
    for line in src.splitlines():
        if len(line) >= 7 and line[6:7] in ("*", "/"):
            continue
        body = line[7:72] if len(line) > 7 else ""
        out.append(body.rstrip())
    return "\n".join(out)


# ── COPY expansion ────────────────────────────────────────────────────────────

_COPY_RE = re.compile(r"^\s*COPY\s+([A-Z0-9][A-Z0-9-]*)\s*\.?", re.IGNORECASE | re.MULTILINE)


def _copy_directives(src: str) -> list[str]:
    return [m.group(1).upper() for m in _COPY_RE.finditer(src)]


def expand_copies(src: str, copybook_index: dict[str, str]) -> tuple[str, list[str]]:
    """Inline resolvable copybooks; unresolved COPY directives are left in place but
    still reported. Returns ``(expanded_src, referenced_members)``."""
    refs = _copy_directives(src)

    def repl(m: re.Match) -> str:
        member = m.group(1).upper()
        return copybook_index.get(member, m.group(0))

    return _COPY_RE.sub(repl, src), refs


# ── structure extraction ──────────────────────────────────────────────────────

_PARA_RE = re.compile(r"^([A-Z0-9][A-Z0-9-]*)\s*\.\s*$", re.IGNORECASE)
_PERFORM_RE = re.compile(r"\bPERFORM\s+([A-Z0-9][A-Z0-9-]*)", re.IGNORECASE)
_CALL_RE = re.compile(r"\bCALL\s+'([^']+)'", re.IGNORECASE)
_GOTO_RE = re.compile(r"\bGO\s+TO\s+([A-Z0-9][A-Z0-9-]*)", re.IGNORECASE)
_DIV_RE = re.compile(r"\b([A-Z]+)\s+DIVISION\s*\.", re.IGNORECASE)
_SECTION_RE = re.compile(r"^([A-Z0-9][A-Z0-9-]*)\s+SECTION\s*\.\s*$", re.IGNORECASE)


def _program_id(src: str) -> str:
    m = re.search(r"PROGRAM-ID\.\s+([A-Z0-9-]+)", src, re.IGNORECASE)
    return m.group(1).upper() if m else "PROGRAM"


def _structure(src: str) -> AstNode:
    lines = src.splitlines()
    root = AstNode(kind="module", name=_program_id(src), metadata={"cobol_kind": "program"})
    in_proc = False
    current: AstNode | None = None
    for i, raw in enumerate(lines):
        line = raw.strip()
        d = _DIV_RE.search(line)
        if d:
            in_proc = d.group(1).upper() == "PROCEDURE"
            current = None
            continue
        if not in_proc or not line:
            continue
        sec = _SECTION_RE.match(line)
        if sec:
            current = AstNode(kind="function", name=sec.group(1).upper(),
                              span=(i + 1, i + 1), metadata={"cobol_kind": "section"})
            root.children.append(current)
            continue
        para = _PARA_RE.match(line)
        if para and not any(rx.search(line) for rx in (_PERFORM_RE, _CALL_RE, _GOTO_RE)):
            current = AstNode(kind="function", name=para.group(1).upper(),
                              span=(i + 1, i + 1), metadata={"cobol_kind": "paragraph"})
            root.children.append(current)
            continue
        if current is None:
            continue
        for m in _PERFORM_RE.finditer(line):
            current.children.append(AstNode(kind="call", name=m.group(1).upper(),
                                            metadata={"cobol_kind": "perform"}))
        for m in _GOTO_RE.finditer(line):
            current.children.append(AstNode(kind="call", name=m.group(1).upper(),
                                            metadata={"cobol_kind": "goto"}))
        for m in _CALL_RE.finditer(line):
            current.children.append(AstNode(kind="call", name=m.group(1).upper(),
                                            metadata={"cobol_kind": "call"}))
    return root


# ── data items ────────────────────────────────────────────────────────────────

_LEVEL_RE = re.compile(r"^\s*(\d\d)\s+([A-Z0-9-]+)(?:\s+PIC\s+(\S+?)\.?)?", re.IGNORECASE)


class CobolFrontend:
    languages = {"cobol"}

    def preprocess(self, path: str, src: str) -> str:
        return _strip_fixed(src) if _detect_format(src) == "fixed" else src

    def structure(self, path: str, src: str) -> AstNode:
        return _structure(self.preprocess(path, src))

    def edges(self, path: str, root: AstNode, src: str) -> list[dict]:
        pre = self.preprocess(path, src)
        prog = root.name
        out: list[dict] = [
            {"source": prog, "target": m, "type": "COPIES"} for m in _copy_directives(pre)
        ]
        # DB2 + CICS relations (defined in mainframe_data to keep this file focused).
        from imperium.intelligence.frontends.mainframe_data import extract_cics, extract_sql_edges

        out.extend(extract_sql_edges(prog, pre))
        out.extend(extract_cics(prog, pre))
        return out

    def data_items(self, path: str, src: str) -> list[dict]:
        out: list[dict] = []
        for line in self.preprocess(path, src).splitlines():
            m = _LEVEL_RE.match(line)
            if m:
                out.append({
                    "level": m.group(1),
                    "name": m.group(2).upper(),
                    "pic": (m.group(3) or "").upper(),
                    "is_condition": m.group(1) == "88",
                })
        return out
