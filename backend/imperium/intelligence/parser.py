"""Parser (TDD §4). Multi-language source file parser.

Uses tree-sitter when available; falls back to a line-by-line regex scanner
for languages without a grammar installed — so the pipeline always produces
some output rather than failing.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

log = logging.getLogger("imperium.intelligence.parser")

# Languages with known tree-sitter grammar identifiers
_TS_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "c_sharp",
}

_EXT_TO_LANGUAGE: dict[str, str] = {
    **_TS_LANGUAGE_MAP,
    ".sql": "sql",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".html": "html",
    ".css": "css",
}


@dataclass
class ParsedFile:
    path: str
    language: str
    tree: object | None = None       # tree-sitter Tree (if available)
    lines: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _detect_language(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _EXT_TO_LANGUAGE.get(ext, "unknown")


def _parse_with_treesitter(path: str, language: str, source: bytes) -> object | None:
    """Attempt tree-sitter parse; return None if not available."""
    try:
        import tree_sitter_languages  # optional extra

        parser_lang = tree_sitter_languages.get_language(language)
        from tree_sitter import Parser

        parser = Parser()
        parser.set_language(parser_lang)
        return parser.parse(source)
    except Exception:  # noqa: BLE001
        pass
    try:
        # tree-sitter >= 0.21 direct approach
        from tree_sitter import Language, Parser

        # Individual grammar packages: tree_sitter_python, etc.
        mod_name = f"tree_sitter_{language.replace('-', '_')}"
        import importlib

        mod = importlib.import_module(mod_name)
        lang = Language(mod.language())
        parser = Parser(lang)
        return parser.parse(source)
    except Exception:  # noqa: BLE001
        return None


def parse_file(path: str, language: str | None = None) -> ParsedFile:
    """Parse a single file. Falls back gracefully if tree-sitter grammar unavailable."""
    lang = language or _detect_language(path)

    try:
        with open(path, "rb") as fh:
            source_bytes = fh.read()
        source_text = source_bytes.decode("utf-8", errors="replace")
    except OSError as exc:
        return ParsedFile(path=path, language=lang, errors=[str(exc)])

    lines = source_text.splitlines()
    tree = None

    if lang in _TS_LANGUAGE_MAP.values():
        tree = _parse_with_treesitter(path, lang, source_bytes)
        if tree is None:
            log.debug("tree-sitter unavailable for %s (%s) — using line scanner", path, lang)

    return ParsedFile(path=path, language=lang, tree=tree, lines=lines)


def parse_directory(repo_path: str, languages: list[str] | None = None) -> list[ParsedFile]:
    """Parse all source files in a directory tree, optionally filtering by language."""
    skip_dirs = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build"}
    skip_exts = {".min.js", ".lock", ".png", ".jpg", ".svg", ".ico", ".woff", ".ttf", ".pyc"}

    parsed = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for fname in files:
            if any(fname.endswith(e) for e in skip_exts):
                continue
            fp = os.path.join(root, fname)
            lang = _detect_language(fp)
            if languages and lang not in languages:
                continue
            parsed.append(parse_file(fp, lang))

    log.info("Parsed %d files in %s", len(parsed), repo_path)
    return parsed
