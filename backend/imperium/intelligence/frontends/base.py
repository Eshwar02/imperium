"""Language frontend protocol.

A frontend owns everything language-specific: how to normalize source, how to turn
it into the shared ``AstNode`` shape, what extra (non-call) graph edges it implies, and
what data items feed the business-rule extractor. The rest of the pipeline stays generic
so legacy languages (COBOL/JCL/DB2/CICS) reuse the existing RKB with no schema change.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from imperium.intelligence.ast_builder import AstNode


@runtime_checkable
class LanguageFrontend(Protocol):
    languages: set[str]

    def preprocess(self, path: str, src: str) -> str:
        """Normalize source before structural analysis (e.g. strip fixed-format cols)."""
        ...

    def structure(self, path: str, src: str) -> AstNode:
        """Return a ``module`` root whose ``function`` children carry ``call`` children,
        so the existing call-graph builder resolves definitions and edges unchanged."""
        ...

    def edges(self, path: str, root: AstNode, src: str) -> list[dict]:
        """Extra non-call relations as ``{"source","target","type"}`` dicts."""
        ...

    def data_items(self, path: str, src: str) -> list[dict]:
        """Structured data declarations that feed the business-rule extractor."""
        ...
