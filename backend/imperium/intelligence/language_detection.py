"""Language Detection (TDD §4). Weighted by manifest files + LOC counts.

Strategy:
  1. Extension-based first pass — count files per language.
  2. LOC-weighted: count lines-of-code per language for better ranking.
  3. Manifest-boost: presence of requirements.txt, package.json, pom.xml, etc.
     strongly boosts the corresponding language's rank.
  4. COBOL support: .cbl/.cob/.cpy per TDD §12.
  5. Returns ranked list of language strings + metadata.
"""
from __future__ import annotations

import os
from collections import Counter, defaultdict

_EXT_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".kt": "kotlin",
    ".swift": "swift",
    ".php": "php",
    ".scala": "scala",
    ".sh": "bash",
    ".bash": "bash",
    ".cbl": "cobol",
    ".cob": "cobol",
    ".cpy": "cobol",
}

# Manifest file → language it implies, with a strong boost multiplier
_MANIFEST_BOOST: dict[str, tuple[str, int]] = {
    "requirements.txt": ("python", 500),
    "requirements-dev.txt": ("python", 200),
    "pyproject.toml": ("python", 500),
    "setup.py": ("python", 400),
    "Pipfile": ("python", 400),
    "package.json": ("javascript", 500),
    "yarn.lock": ("javascript", 200),
    "pom.xml": ("java", 500),
    "build.gradle": ("java", 400),
    "go.mod": ("go", 500),
    "Cargo.toml": ("rust", 500),
    "Gemfile": ("ruby", 500),
    "composer.json": ("php", 500),
    "*.csproj": ("csharp", 500),
    "*.sln": ("csharp", 300),
}

_SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build"}


def detect(repo_path: str) -> list[str]:
    """Return ranked list of language names (most prominent first).

    Ranking combines: LOC count × language weight + manifest boost.
    """
    loc_by_lang: dict[str, int] = defaultdict(int)
    manifest_boosts: dict[str, int] = defaultdict(int)

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            fp = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()

            # Manifest boost
            for manifest_name, (lang, boost) in _MANIFEST_BOOST.items():
                if manifest_name.startswith("*"):
                    # Glob-style: match extension
                    if fname.endswith(manifest_name[1:]):
                        manifest_boosts[lang] += boost
                elif fname == manifest_name:
                    manifest_boosts[lang] += boost

            # LOC count for known languages
            lang = _EXT_LANG.get(ext)
            if not lang:
                continue

            try:
                with open(fp, encoding="utf-8", errors="ignore") as fh:
                    loc = sum(1 for line in fh if line.strip())
                loc_by_lang[lang] += loc
            except OSError:
                loc_by_lang[lang] += 1  # count file even if unreadable

    # Combine scores
    all_langs = set(loc_by_lang) | set(manifest_boosts)
    scores: dict[str, int] = {
        lang: loc_by_lang.get(lang, 0) + manifest_boosts.get(lang, 0)
        for lang in all_langs
    }

    return [lang for lang, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def detect_with_stats(repo_path: str) -> list[dict]:
    """Return [{language, loc, files, manifest_detected}] sorted by prominence."""
    loc_by_lang: dict[str, int] = defaultdict(int)
    files_by_lang: dict[str, int] = defaultdict(int)
    manifest_langs: set[str] = set()

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            fp = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()

            # Manifest detection
            for manifest_name, (lang, _) in _MANIFEST_BOOST.items():
                if manifest_name.startswith("*"):
                    if fname.endswith(manifest_name[1:]):
                        manifest_langs.add(lang)
                elif fname == manifest_name:
                    manifest_langs.add(lang)

            lang = _EXT_LANG.get(ext)
            if not lang:
                continue

            files_by_lang[lang] += 1
            try:
                with open(fp, encoding="utf-8", errors="ignore") as fh:
                    loc = sum(1 for line in fh if line.strip())
                loc_by_lang[lang] += loc
            except OSError:
                pass

    all_langs = set(loc_by_lang) | manifest_langs
    result = [
        {
            "language": lang,
            "loc": loc_by_lang.get(lang, 0),
            "files": files_by_lang.get(lang, 0),
            "manifest_detected": lang in manifest_langs,
        }
        for lang in all_langs
    ]
    return sorted(result, key=lambda x: x["loc"] + (500 if x["manifest_detected"] else 0), reverse=True)
