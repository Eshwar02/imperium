"""Documentation Extractor (TDD §4). Pulls existing docs/comments/docstrings.

Collects READMEs, docstrings, inline comments as the 'documented' baseline —
contrasted against extracted implicit rules to find documentation rot.
Also generates per-module summaries via LLM for the memory hierarchy.
"""
from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("imperium.intelligence.doc_extractor")

_DOCSTRING_RE = re.compile(
    r'(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')',
    re.DOTALL,
)
_COMMENT_RE = re.compile(r"#.*$", re.MULTILINE)
_JS_COMMENT_RE = re.compile(r"//.*$|/\*.*?\*/", re.DOTALL | re.MULTILINE)

_README_NAMES = {"README.md", "README.rst", "README.txt", "README", "readme.md"}


def _extract_docstrings(source: str, language: str) -> list[str]:
    """Extract docstrings / multi-line comments from source."""
    if language == "python":
        return [
            m.group(1) or m.group(2)
            for m in _DOCSTRING_RE.finditer(source)
            if (m.group(1) or m.group(2)).strip()
        ]
    if language in ("javascript", "typescript", "java", "go", "c", "cpp", "c_sharp"):
        # JSDoc / block comments
        return [
            m.group().strip("/*\n ")
            for m in re.finditer(r"/\*\*?(.*?)\*/", source, re.DOTALL)
            if m.group().strip()
        ]
    return []


def _extract_comments(source: str, language: str) -> list[str]:
    if language == "python":
        return [m.group().lstrip("#").strip() for m in _COMMENT_RE.finditer(source) if m.group().strip("#").strip()]
    if language in ("javascript", "typescript", "java", "go"):
        return [m.group().lstrip("/").strip() for m in re.finditer(r"//(.*)$", source, re.MULTILINE)]
    return []


def _walk_source_files(repo_path: str):
    """Yield (file_path, language) for all source files."""
    skip_dirs = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build"}
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "javascript", ".tsx": "typescript", ".java": "java",
        ".go": "go", ".rs": "rust", ".cs": "c_sharp", ".rb": "ruby",
    }
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in ext_map:
                yield os.path.join(root, fname), ext_map[ext]


def extract(repo_path: str) -> dict:
    """Return {readmes, docstrings, comments, module_summaries}.

    - readmes: list of {path, content}
    - docstrings: list of {file, text}
    - comments: list of {file, text}
    """
    readmes: list[dict] = []
    docstrings: list[dict] = []
    comments: list[dict] = []
    module_summaries: dict[str, str] = {}

    # Collect READMEs
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != ".git"]
        for fname in files:
            if fname in _README_NAMES:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                    readmes.append({"path": fpath, "content": content})
                except OSError:
                    pass

    # Collect docstrings + comments from source files
    for fpath, lang in _walk_source_files(repo_path):
        try:
            with open(fpath, encoding="utf-8", errors="ignore") as fh:
                source = fh.read()
        except OSError:
            continue

        for ds in _extract_docstrings(source, lang):
            docstrings.append({"file": fpath, "language": lang, "text": ds[:2000]})

        for cm in _extract_comments(source, lang)[:20]:   # cap per file
            if len(cm) > 10:
                comments.append({"file": fpath, "language": lang, "text": cm[:500]})

        # Per-module summary: first docstring or first N lines
        rel = os.path.relpath(fpath, repo_path)
        module_key = rel.split(os.sep)[0]
        if module_key not in module_summaries:
            ds_list = _extract_docstrings(source, lang)
            if ds_list:
                module_summaries[module_key] = ds_list[0][:500]
            else:
                module_summaries[module_key] = source[:300]

    log.info(
        "doc_extractor: %d readmes, %d docstrings, %d comments from %s",
        len(readmes), len(docstrings), len(comments), repo_path,
    )
    return {
        "readmes": readmes,
        "docstrings": docstrings,
        "comments": comments,
        "module_summaries": module_summaries,
    }


def generate_llm_summary(module_path: str, source_excerpt: str) -> str:
    """Ask the documentation LLM to summarize a module/file."""
    from imperium.llm.client import complete

    prompt = (
        f"Module: {module_path}\n\n"
        f"Source excerpt:\n```\n{source_excerpt[:3000]}\n```\n\n"
        "Write a concise 2-3 sentence summary of what this module does, "
        "its responsibilities, and its public interface."
    )
    try:
        return complete("documentation", prompt, temperature=0.1)
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM summary failed for %s: %s", module_path, exc)
        return f"[summary unavailable: {exc}]"
