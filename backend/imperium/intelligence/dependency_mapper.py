"""Dependency Mapper (TDD §4). Maps internal + external dependencies.

Parses manifest files (requirements.txt, package.json, pom.xml, go.mod, etc.),
resolves versions, and flags deprecated/CVE-bearing dependencies.
Feeds security_scanner + research agents.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

log = logging.getLogger("imperium.intelligence.dependency_mapper")


@dataclass
class Dependency:
    name: str
    version: str | None
    ecosystem: str   # python | npm | maven | go | cargo | rubygems
    direct: bool
    path: str        # manifest file path
    extras: dict = field(default_factory=dict)


# ── Manifest parsers ──────────────────────────────────────────────────────────

_REQ_LINE = re.compile(r"^([A-Za-z0-9_.\-\[\]]+)\s*([><=!~^]+\s*[\d.*,]+)?")


def _parse_requirements_txt(path: str) -> list[Dependency]:
    deps = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-r"):
                    continue
                m = _REQ_LINE.match(line)
                if m:
                    deps.append(Dependency(
                        name=m.group(1),
                        version=m.group(2).strip() if m.group(2) else None,
                        ecosystem="python",
                        direct=True,
                        path=path,
                    ))
    except OSError:
        pass
    return deps


def _parse_pyproject_toml(path: str) -> list[Dependency]:
    deps = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
        # Extract dependencies = ["pkg>=x.y"] sections
        dep_block = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if dep_block:
            for item in re.findall(r'"([^"]+)"', dep_block.group(1)):
                m = _REQ_LINE.match(item)
                if m:
                    deps.append(Dependency(
                        name=m.group(1),
                        version=m.group(2).strip() if m.group(2) else None,
                        ecosystem="python",
                        direct=True,
                        path=path,
                    ))
    except OSError:
        pass
    return deps


def _parse_package_json(path: str) -> list[Dependency]:
    deps = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            data = json.load(fh)
        for dep_type, is_direct in [("dependencies", True), ("devDependencies", False)]:
            for name, version in data.get(dep_type, {}).items():
                deps.append(Dependency(
                    name=name,
                    version=version,
                    ecosystem="npm",
                    direct=is_direct,
                    path=path,
                ))
    except (OSError, json.JSONDecodeError):
        pass
    return deps


def _parse_pom_xml(path: str) -> list[Dependency]:
    deps = []
    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(path)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        for dep in tree.findall(".//m:dependency", ns) + tree.findall(".//dependency"):
            group = dep.findtext("groupId") or dep.findtext("m:groupId", namespaces=ns) or ""
            artifact = dep.findtext("artifactId") or dep.findtext("m:artifactId", namespaces=ns) or ""
            version = dep.findtext("version") or dep.findtext("m:version", namespaces=ns)
            if group and artifact:
                deps.append(Dependency(
                    name=f"{group}:{artifact}",
                    version=version,
                    ecosystem="maven",
                    direct=True,
                    path=path,
                ))
    except Exception:  # noqa: BLE001
        pass
    return deps


def _parse_go_mod(path: str) -> list[Dependency]:
    deps = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                m = re.match(r"^require\s+(\S+)\s+(\S+)", line) or re.match(r"^\s+(\S+)\s+(v[\d.]+\S*)", line)
                if m:
                    deps.append(Dependency(
                        name=m.group(1),
                        version=m.group(2),
                        ecosystem="go",
                        direct=True,
                        path=path,
                    ))
    except OSError:
        pass
    return deps


def _parse_cargo_toml(path: str) -> list[Dependency]:
    deps = []
    try:
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        for m in re.finditer(r'^(\w[\w-]*)\s*=\s*["\{]([^"\}\n]+)', content, re.MULTILINE):
            deps.append(Dependency(
                name=m.group(1),
                version=m.group(2).strip(),
                ecosystem="cargo",
                direct=True,
                path=path,
            ))
    except OSError:
        pass
    return deps


# ── Manifest discovery ────────────────────────────────────────────────────────

_MANIFEST_HANDLERS: dict[str, callable] = {
    "requirements.txt": _parse_requirements_txt,
    "requirements-dev.txt": _parse_requirements_txt,
    "requirements-test.txt": _parse_requirements_txt,
    "pyproject.toml": _parse_pyproject_toml,
    "package.json": _parse_package_json,
    "pom.xml": _parse_pom_xml,
    "go.mod": _parse_go_mod,
    "Cargo.toml": _parse_cargo_toml,
}


def map_dependencies(repo_path: str) -> list[dict]:
    """Walk repo, parse all manifests, return flat list of dependency dicts.

    Returns [{name, version, ecosystem, direct, path}].
    """
    all_deps: list[Dependency] = []
    skip_dirs = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build"}

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for fname in files:
            handler = _MANIFEST_HANDLERS.get(fname)
            if handler:
                fpath = os.path.join(root, fname)
                found = handler(fpath)
                all_deps.extend(found)
                log.debug("Parsed %d deps from %s", len(found), fpath)

    log.info("Mapped %d dependencies in %s", len(all_deps), repo_path)
    return [
        {
            "name": d.name,
            "version": d.version,
            "ecosystem": d.ecosystem,
            "direct": d.direct,
            "path": d.path,
        }
        for d in all_deps
    ]
