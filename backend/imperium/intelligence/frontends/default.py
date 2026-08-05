"""Default frontend — wraps the existing tree-sitter/regex + ast_builder path.

Behavior-preserving for all modern languages: it simply reuses ``parse_file`` and
``ast_builder.build``. Registered for nothing, so it is the fallback returned by
``get_frontend`` for any language without a dedicated frontend.
"""
from __future__ import annotations

from imperium.intelligence.ast_builder import AstNode, build
from imperium.intelligence.parser import parse_file


class DefaultFrontend:
    languages: set[str] = set()

    def preprocess(self, path: str, src: str) -> str:
        return src

    def structure(self, path: str, src: str) -> AstNode:
        return build(parse_file(path))

    def edges(self, path: str, root: AstNode, src: str) -> list[dict]:
        return []

    def data_items(self, path: str, src: str) -> list[dict]:
        return []
