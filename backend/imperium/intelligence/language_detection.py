"""Language Detection (TDD §4). Extension-based, weighted by lines of code and by
manifest files, ranked. Handles COBOL (.cbl/.cob/.cpy) per TDD §12.

``detect`` returns languages ranked most-significant-first (by LOC, with a boost for
languages whose ecosystem manifest is present). ``detect_detailed`` returns the same
ranking with per-language file + LOC counts.
"""
from __future__ import annotations

import os
from collections import defaultdict

_EXT_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".php": "php",
    ".cs": "csharp",
    ".cbl": "cobol",
    ".cob": "cobol",
    ".cpy": "cobol",
}
# Manifest filename → language it signals (a present manifest boosts that language).
_MANIFEST_LANG = {
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "setup.py": "python",
    "package.json": "javascript",
    "tsconfig.json": "typescript",
    "pom.xml": "java",
    "build.gradle": "java",
    "go.mod": "go",
    "Gemfile": "ruby",
    "Cargo.toml": "rust",
    "composer.json": "php",
}
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
_MANIFEST_BOOST = 500  # LOC-equivalent weight for a present manifest


def detect_detailed(repo_path: str) -> list[dict]:
    """Return [{language, files, loc, weight}] ranked by weight (loc + manifest boost)."""
    files_by_lang: dict[str, int] = defaultdict(int)
    loc_by_lang: dict[str, int] = defaultdict(int)
    manifests: set[str] = set()

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if name in _MANIFEST_LANG:
                manifests.add(_MANIFEST_LANG[name])
            lang = _EXT_LANG.get(os.path.splitext(name)[1].lower())
            if not lang:
                continue
            files_by_lang[lang] += 1
            try:
                with open(os.path.join(root, name), encoding="utf-8", errors="replace") as fh:
                    loc_by_lang[lang] += sum(1 for _ in fh)
            except OSError:
                pass

    result = []
    for lang in set(files_by_lang) | manifests:
        weight = loc_by_lang.get(lang, 0) + (_MANIFEST_BOOST if lang in manifests else 0)
        result.append(
            {
                "language": lang,
                "files": files_by_lang.get(lang, 0),
                "loc": loc_by_lang.get(lang, 0),
                "weight": weight,
            }
        )
    result.sort(key=lambda d: d["weight"], reverse=True)
    return result


def detect(repo_path: str) -> list[str]:
    """Return languages present, ranked most-significant-first."""
    return [d["language"] for d in detect_detailed(repo_path) if d["weight"] > 0]
