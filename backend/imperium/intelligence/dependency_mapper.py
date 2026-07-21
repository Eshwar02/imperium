"""Dependency Mapper (TDD §4). Maps internal + external dependencies.

TODO(team): parse manifests (requirements.txt, package.json, pom.xml), resolve
versions, flag deprecated/CVE-bearing deps (feeds security_scanner + research).
"""
from __future__ import annotations


def map_dependencies(repo_path: str) -> list[dict]:
    """Return [{name, version, ecosystem, direct, path}]. TODO(team)."""
    raise NotImplementedError("dependency mapping — team task")
