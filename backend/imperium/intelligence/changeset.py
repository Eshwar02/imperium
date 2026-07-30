"""Changeset Organizer (§1.2).

Groups and structures the set of files a transformation touches — not a flat list.
Clustering strategy:
  1. Module/domain cluster: top-level directory prefix
  2. Call-graph proximity: shared Neo4j edges (co-called / co-depended)
  3. Shared business rules: files that contain the same rule appear in one cluster

Produces a ChangesetManifest + ChangesetFile rows consumed by Transformation +
Documentation agents.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

log = logging.getLogger("imperium.intelligence.changeset")


@dataclass
class FileEntry:
    file_path: str
    module_prefix: str = ""         # top-level dir / first path segment
    rule_ids: list[str] = field(default_factory=list)
    blast_radius_node_ids: list[str] = field(default_factory=list)
    call_graph_proximity: float = 0.0


@dataclass
class Cluster:
    label: str
    files: list[FileEntry]
    shared_rule_ids: list[str] = field(default_factory=list)


def _module_prefix(path: str) -> str:
    """Return the top-level directory of a file path as domain label."""
    parts = path.replace("\\", "/").split("/")
    return parts[0] if parts else path


def _build_rule_index(rules_by_file: dict[str, list[str]]) -> dict[str, list[str]]:
    """Invert: rule_id → [file_paths]."""
    index: dict[str, list[str]] = defaultdict(list)
    for path, rule_ids in rules_by_file.items():
        for rid in rule_ids:
            index[rid].append(path)
    return dict(index)


def cluster_by_module(entries: list[FileEntry]) -> list[Cluster]:
    """Group files by top-level directory (module/domain)."""
    groups: dict[str, list[FileEntry]] = defaultdict(list)
    for e in entries:
        groups[e.module_prefix].append(e)
    return [Cluster(label=label, files=files) for label, files in sorted(groups.items())]


def cluster_by_shared_rules(entries: list[FileEntry], rules_by_file: dict[str, list[str]]) -> list[Cluster]:
    """Group files that share business rules.

    Uses a simple union-find so files sharing ANY rule end up in the same cluster.
    """
    file_map = {e.file_path: i for i, e in enumerate(entries)}
    parent = list(range(len(entries)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    rule_index = _build_rule_index(rules_by_file)
    for rule_id, paths in rule_index.items():
        indices = [file_map[p] for p in paths if p in file_map]
        for i in range(1, len(indices)):
            union(indices[0], indices[i])

    groups: dict[int, list[FileEntry]] = defaultdict(list)
    for entry in entries:
        root = find(file_map[entry.file_path])
        groups[root].append(entry)

    clusters = []
    for root, cluster_entries in groups.items():
        # Shared rules = union of all rule_ids in this cluster
        all_rules: set[str] = set()
        for e in cluster_entries:
            all_rules.update(e.rule_ids)
        label = cluster_entries[0].module_prefix if cluster_entries else str(root)
        clusters.append(Cluster(label=label, files=cluster_entries, shared_rule_ids=sorted(all_rules)))

    return clusters


def enrich_with_proximity(entries: list[FileEntry], repository_id: str) -> list[FileEntry]:
    """Query Neo4j to set call_graph_proximity scores.

    Proximity = number of shared graph edges / total edges (normalised).
    Gracefully skips if Neo4j is unavailable.
    """
    try:
        from imperium.rkb.graph import blast_radius

        for entry in entries:
            try:
                br = blast_radius(entry.file_path, depth=2)
                entry.blast_radius_node_ids = [r.get("id", "") for r in br]
                entry.call_graph_proximity = min(len(br) / 20.0, 1.0)
            except Exception:  # noqa: BLE001
                pass
    except ImportError:
        pass
    return entries


def build_changeset(
    repository_id: str,
    file_paths: list[str],
    name: str = "auto",
    description: str | None = None,
    persist: bool = True,
) -> dict:
    """Build and optionally persist a changeset manifest.

    Args:
        repository_id: The repository being transformed.
        file_paths: Flat list of files the transformation touches.
        name: Manifest name / label.
        description: Human-readable description.
        persist: Write ChangesetManifest + ChangesetFile rows to Postgres.

    Returns dict with {manifest_id, clusters, files}.
    """
    # Fetch rule associations from Postgres
    rules_by_file: dict[str, list[str]] = defaultdict(list)
    try:
        from imperium.rkb.store import get_business_rules, get_session

        session = get_session()
        try:
            rules = get_business_rules(session, repository_id)
            for rule in rules:
                for loc in rule.locations:
                    fp = loc if isinstance(loc, str) else loc.get("file", "")
                    if fp in file_paths:
                        rules_by_file[fp].append(rule.id)
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not fetch business rules for changeset: %s", exc)

    entries = [
        FileEntry(
            file_path=fp,
            module_prefix=_module_prefix(fp),
            rule_ids=rules_by_file.get(fp, []),
        )
        for fp in file_paths
    ]

    entries = enrich_with_proximity(entries, repository_id)

    # Primary clustering: module/domain
    module_clusters = cluster_by_module(entries)
    # Secondary clustering: shared rules (within each module cluster)
    rule_clusters = cluster_by_shared_rules(entries, dict(rules_by_file))

    # Flatten for persistence — use module cluster label as primary
    files_for_manifest = []
    cluster_by_path = {e.file_path: c.label for c in module_clusters for e in c.files}
    for entry in entries:
        # Find shared rules from rule clustering
        shared = []
        for c in rule_clusters:
            if any(e.file_path == entry.file_path for e in c.files):
                shared = c.shared_rule_ids
                break
        files_for_manifest.append({
            "file_path": entry.file_path,
            "cluster_label": cluster_by_path.get(entry.file_path, ""),
            "call_graph_proximity": entry.call_graph_proximity,
            "shared_rule_ids": shared,
        })

    manifest_id = None
    if persist:
        try:
            from imperium.rkb.store import create_changeset, get_session

            session = get_session()
            try:
                manifest = create_changeset(
                    session=session,
                    repository_id=repository_id,
                    name=name,
                    files=files_for_manifest,
                    description=description,
                )
                manifest_id = manifest.id
                log.info(
                    "Created changeset manifest %s with %d files for repo %s",
                    manifest_id, len(file_paths), repository_id,
                )
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not persist changeset: %s", exc)

    return {
        "manifest_id": manifest_id,
        "repository_id": repository_id,
        "name": name,
        "clusters": [
            {
                "label": c.label,
                "files": [e.file_path for e in c.files],
                "shared_rule_ids": c.shared_rule_ids,
            }
            for c in rule_clusters
        ],
        "files": files_for_manifest,
    }
