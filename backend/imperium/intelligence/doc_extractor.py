"""Documentation Extractor (TDD §4). Pulls existing docs/comments/docstrings.

TODO(team): collect READMEs, docstrings, inline comments as the 'documented'
baseline — contrast against extracted implicit rules to find documentation rot.
"""
from __future__ import annotations


def extract(repo_path: str) -> dict:
    """Return {readmes, docstrings, comments}. TODO(team)."""
    raise NotImplementedError("doc extraction — team task")
