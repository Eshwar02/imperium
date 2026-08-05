"""JCL frontend — jobs, steps, programs, datasets.

Parses the mainframe job control that ties COBOL programs to the data they run against:
  //JOBNAME JOB ...            → module (JclJob)
  //STEP    EXEC PGM=PROG      → function (JclStep) + RUNS(step → PROG)
  //DD      DD DSN=DATASET     → USES_DATASET(step → DATASET)
Emitting steps as ``function`` nodes lets them land in the call-graph write path.
"""
from __future__ import annotations

import re

from imperium.intelligence.ast_builder import AstNode

_JOB_RE = re.compile(r"^//([A-Z0-9#@$]+)\s+JOB\b", re.IGNORECASE)
_STEP_RE = re.compile(r"^//([A-Z0-9#@$]+)\s+EXEC\s+(.+)$", re.IGNORECASE)
_PGM_RE = re.compile(r"\bPGM=([A-Z0-9#@$]+)", re.IGNORECASE)
_DD_RE = re.compile(r"^//([A-Z0-9#@$]+)\s+DD\s+(.+)$", re.IGNORECASE)
_DSN_RE = re.compile(r"\bDSN=([A-Z0-9#@$.\-()]+)", re.IGNORECASE)


def _job_name(src: str) -> str:
    for line in src.splitlines():
        m = _JOB_RE.match(line)
        if m:
            return m.group(1).upper()
    return "JOB"


class JclFrontend:
    languages = {"jcl"}

    def preprocess(self, path: str, src: str) -> str:
        return src

    def structure(self, path: str, src: str) -> AstNode:
        root = AstNode(kind="module", name=_job_name(src), metadata={"jcl_kind": "job"})
        for i, line in enumerate(src.splitlines()):
            m = _STEP_RE.match(line)
            if m:
                root.children.append(AstNode(
                    kind="function", name=m.group(1).upper(), span=(i + 1, i + 1),
                    metadata={"jcl_kind": "step"}))
        return root

    def edges(self, path: str, root: AstNode, src: str) -> list[dict]:
        edges: list[dict] = []
        current_step: str | None = None
        for line in src.splitlines():
            s = _STEP_RE.match(line)
            if s:
                current_step = s.group(1).upper()
                pgm = _PGM_RE.search(s.group(2))
                if pgm:
                    edges.append({"source": current_step, "target": pgm.group(1).upper(),
                                  "type": "RUNS"})
                continue
            d = _DD_RE.match(line)
            if d and current_step:
                dsn = _DSN_RE.search(d.group(2))
                if dsn:
                    edges.append({"source": current_step, "target": dsn.group(1).upper(),
                                  "type": "USES_DATASET"})
        return edges

    def data_items(self, path: str, src: str) -> list[dict]:
        return []
