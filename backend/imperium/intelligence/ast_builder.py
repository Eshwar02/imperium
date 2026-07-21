"""AST Builder (TDD §4). Normalizes tree-sitter CSTs into a language-agnostic AST.

TODO(team): map per-language nodes → common node kinds (Module, Class, Function,
Call, Import) so downstream mappers stay language-neutral.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from imperium.intelligence.parser import ParsedFile


@dataclass
class AstNode:
    kind: str
    name: str
    span: tuple[int, int] = (0, 0)
    children: list["AstNode"] = field(default_factory=list)


def build(parsed: ParsedFile) -> AstNode:
    raise NotImplementedError("AST normalization — team task")
