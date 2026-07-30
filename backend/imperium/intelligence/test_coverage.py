"""Test Coverage Analyzer (TDD §4). Maps existing tests → code, finds gaps.

Discovers test files and their frameworks, infers which source modules are covered
(by naming convention — ``test_foo.py``/``foo_test.py``/``foo.spec.ts`` → ``foo``),
and reports source modules with no apparent test. Feeds the Test-Generation agent's
baseline pass (PRD §10) so it targets gaps rather than generic boilerplate.
"""
from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("imperium.intelligence.test_coverage")

_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
_SRC_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java"}
_TEST_NAME = re.compile(r"(?:^test_(.+)|(.+)_test|(.+)\.spec|(.+)\.test)$")
_FRAMEWORK_HINTS = {
    "pytest": re.compile(r"\b(import pytest|def test_)"),
    "unittest": re.compile(r"\bimport unittest\b"),
    "jest": re.compile(r"\b(describe|it|test)\s*\("),
    "vitest": re.compile(r"from ['\"]vitest['\"]"),
    "go-test": re.compile(r"func Test\w+\(t \*testing\.T\)"),
}


def _is_test_file(name: str) -> str | None:
    """Return the covered base stem if ``name`` looks like a test file, else None."""
    stem, ext = os.path.splitext(name)
    if ext.lower() not in _SRC_EXTS:
        return None
    m = _TEST_NAME.match(stem)
    if not m:
        return None
    return next((g for g in m.groups() if g), None)


def analyze(repo_path: str) -> dict:
    """Return {frameworks, covered_modules, gaps, test_files, source_files}."""
    frameworks: set[str] = set()
    covered: set[str] = set()
    source_stems: dict[str, str] = {}  # stem -> relpath
    test_files: list[str] = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in _SRC_EXTS:
                continue
            rel = os.path.relpath(os.path.join(root, name), repo_path)
            covered_stem = _is_test_file(name)
            if covered_stem is not None:
                test_files.append(rel)
                covered.add(covered_stem)
                try:
                    with open(os.path.join(root, name), encoding="utf-8", errors="replace") as fh:
                        head = fh.read(4000)
                    for fw, pat in _FRAMEWORK_HINTS.items():
                        if pat.search(head):
                            frameworks.add(fw)
                except OSError:
                    pass
            else:
                source_stems[os.path.splitext(name)[0]] = rel

    gaps = sorted(rel for stem, rel in source_stems.items() if stem not in covered)
    return {
        "frameworks": sorted(frameworks),
        "covered_modules": sorted(covered),
        "gaps": gaps,
        "test_files": sorted(test_files),
        "source_files": len(source_stems),
    }
