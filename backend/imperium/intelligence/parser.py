"""Parser (TDD §4). tree-sitter multi-language front end (PRD §13).

TODO(team): load tree-sitter grammars per detected language, parse files to
concrete syntax trees, hand to ast_builder.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedFile:
    path: str
    language: str
    tree: object | None = None       # tree-sitter Tree
    errors: list[str] = field(default_factory=list)


def parse_file(path: str, language: str) -> ParsedFile:
    raise NotImplementedError("tree-sitter parse — team task")
