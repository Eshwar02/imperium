"""Transformation Priority Score (§1.1).

Computes a rankable score per file/module that tells the Transformation agent
what to modernize first.

Factors:
  - blast_radius    : number of Neo4j dependents (CALLS/DEPENDS_ON traversal)
  - rule_density    : number of business rules touching this file
  - rule_confidence : mean confidence of those rules (inverted — low conf = higher priority)
  - ai_authorship   : Module.ai_authorship_pct
  - churn           : normalized commits-per-month from timeline
  - age_days        : days since first commit
  - security_debt   : security/tech-debt findings count from analysis
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("imperium.intelligence.priority")

# Weights — tunable; must sum ≤ 1 (remaining weight is reserved for future factors)
_WEIGHTS = {
    "blast_radius": 0.30,
    "rule_density": 0.20,
    "low_confidence_rules": 0.15,
    "ai_authorship": 0.15,
    "churn": 0.10,
    "security_debt": 0.10,
}

_CONFIDENCE_THRESHOLD = 0.70  # rules below this raise priority


@dataclass
class PriorityInput:
    """All signals needed to score a single file."""
    file_path: str
    repository_id: str
    blast_radius_count: int = 0
    business_rule_count: int = 0
    low_confidence_rule_count: int = 0
    mean_rule_confidence: float = 1.0
    ai_authorship_pct: float = 0.0
    commits_per_month: float = 0.0
    age_days: int = 0
    security_finding_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PriorityScore:
    file_path: str
    score: float
    factor_breakdown: dict[str, float]
    blast_radius_count: int
    business_rule_density: float
    business_rule_confidence: float
    ai_authorship_pct: float
    churn_score: float
    age_days: int
    security_debt_score: float


def _normalize(value: float, max_value: float) -> float:
    """Clamp to [0, 1]."""
    if max_value <= 0:
        return 0.0
    return min(value / max_value, 1.0)


def compute_score(inp: PriorityInput, max_blast: int = 100, max_churn: float = 10.0) -> PriorityScore:
    """Compute a priority score in [0, 1] for a single file."""
    blast_norm = _normalize(inp.blast_radius_count, max_blast)
    density_norm = _normalize(inp.business_rule_count, 20)
    # Low-confidence rules are risky → higher priority
    low_conf_norm = _normalize(inp.low_confidence_rule_count, 10)
    ai_norm = inp.ai_authorship_pct / 100.0
    churn_norm = _normalize(inp.commits_per_month, max_churn)
    security_norm = _normalize(inp.security_finding_count, 20)

    breakdown = {
        "blast_radius": blast_norm * _WEIGHTS["blast_radius"],
        "rule_density": density_norm * _WEIGHTS["rule_density"],
        "low_confidence_rules": low_conf_norm * _WEIGHTS["low_confidence_rules"],
        "ai_authorship": ai_norm * _WEIGHTS["ai_authorship"],
        "churn": churn_norm * _WEIGHTS["churn"],
        "security_debt": security_norm * _WEIGHTS["security_debt"],
    }
    total = sum(breakdown.values())

    return PriorityScore(
        file_path=inp.file_path,
        score=round(total, 4),
        factor_breakdown=breakdown,
        blast_radius_count=inp.blast_radius_count,
        business_rule_density=density_norm,
        business_rule_confidence=inp.mean_rule_confidence,
        ai_authorship_pct=inp.ai_authorship_pct,
        churn_score=churn_norm,
        age_days=inp.age_days,
        security_debt_score=security_norm,
    )


def compute_scores_for_repo(
    repository_id: str,
    inputs: list[PriorityInput],
) -> list[PriorityScore]:
    """Score all files in a repo and return them sorted highest-first."""
    if not inputs:
        return []

    max_blast = max((i.blast_radius_count for i in inputs), default=1) or 1
    max_churn = max((i.commits_per_month for i in inputs), default=1.0) or 1.0

    scores = [compute_score(inp, max_blast=max_blast, max_churn=max_churn) for inp in inputs]
    return sorted(scores, key=lambda s: s.score, reverse=True)


def build_priority_inputs_from_rkb(
    repository_id: str,
) -> list[PriorityInput]:
    """Assemble PriorityInput objects from Postgres + Neo4j for all files in a repo.

    Pulls:
      - business rules per file from Postgres
      - blast radius from Neo4j graph
      - churn + age from timeline events (first commit date → age_days)
      - ai_authorship from Module rows
      - security finding count from security_scanner
    """
    import datetime as dt

    from imperium.rkb import graph as neo4j_graph
    from imperium.rkb.store import get_business_rules, get_modules, get_session, get_timeline

    session = get_session()
    try:
        rules = get_business_rules(session, repository_id)
        modules = get_modules(session, repository_id)
        events = get_timeline(session, repository_id)
    finally:
        session.close()

    # Index rules by file path
    rules_by_file: dict[str, list] = {}
    for rule in rules:
        for loc in rule.locations:
            fp = loc if isinstance(loc, str) else loc.get("file", "")
            rules_by_file.setdefault(fp, []).append(rule)

    # Churn + age_days: derive from timeline events per file
    churn_by_file: dict[str, float] = {}
    first_commit_by_file: dict[str, dt.datetime] = {}
    for event in events:
        for fp in event.files_changed:
            path = fp if isinstance(fp, str) else fp.get("path", "")
            lines = 1 if isinstance(fp, str) else fp.get("lines", 1)
            churn_by_file[path] = churn_by_file.get(path, 0) + lines
            if event.committed_at and (
                path not in first_commit_by_file
                or event.committed_at < first_commit_by_file[path]
            ):
                first_commit_by_file[path] = event.committed_at

    now = dt.datetime.utcnow()
    total_months = max(len(events) / 4, 1)  # rough monthly normalization

    module_by_path: dict[str, Any] = {m.path: m for m in modules}

    # Security findings per file — run scanner if repo_path is available
    security_by_file: dict[str, int] = {}
    try:
        from imperium.rkb.store import get_repository, get_session as _gs
        import os
        from imperium.config import get_settings

        _session = _gs()
        try:
            repo = get_repository(_session, repository_id)
        finally:
            _session.close()

        if repo:
            repo_path = os.path.join(get_settings().workspace_dir, repository_id)
            if os.path.isdir(repo_path):
                from imperium.intelligence.security_scanner import scan

                sec_findings = scan(repo_path)
                for sf in sec_findings:
                    for loc in sf.locations:
                        # loc is "file:line" — strip line number
                        file_part = loc.split(":")[0]
                        # Normalise to relative path
                        rel = os.path.relpath(file_part, repo_path) if repo_path else file_part
                        security_by_file[rel] = security_by_file.get(rel, 0) + 1
    except Exception:  # noqa: BLE001
        pass  # security scan is best-effort

    all_paths = set(rules_by_file) | set(churn_by_file) | {m.path for m in modules}

    inputs = []
    for fp in all_paths:
        file_rules = rules_by_file.get(fp, [])
        module = module_by_path.get(fp)
        rule_confidences = [r.confidence for r in file_rules] or [1.0]
        low_conf = sum(1 for r in file_rules if r.confidence < _CONFIDENCE_THRESHOLD)
        mean_conf = sum(rule_confidences) / len(rule_confidences)

        # Blast radius from Neo4j — use file path as node id heuristic
        try:
            br = neo4j_graph.blast_radius(fp)
        except Exception:  # noqa: BLE001
            br = []

        churn = churn_by_file.get(fp, 0) / total_months

        # Age in days from first commit touching this file
        first_commit = first_commit_by_file.get(fp)
        age_days = (now - first_commit).days if first_commit else 0

        inputs.append(PriorityInput(
            file_path=fp,
            repository_id=repository_id,
            blast_radius_count=len(br),
            business_rule_count=len(file_rules),
            low_confidence_rule_count=low_conf,
            mean_rule_confidence=mean_conf,
            ai_authorship_pct=module.ai_authorship_pct if module else 0.0,
            commits_per_month=churn,
            age_days=age_days,
            security_finding_count=security_by_file.get(fp, 0),
        ))

    return inputs


def persist_scores(repository_id: str, scores: list[PriorityScore]) -> None:
    """Write scores to Postgres transformation_priority table."""
    from imperium.rkb.store import get_session, upsert_priority

    session = get_session()
    try:
        for s in scores:
            upsert_priority(
                session=session,
                repository_id=repository_id,
                file_path=s.file_path,
                score=s.score,
                factor_breakdown=s.factor_breakdown,
                blast_radius_count=s.blast_radius_count,
                business_rule_density=s.business_rule_density,
                business_rule_confidence=s.business_rule_confidence,
                ai_authorship_pct=s.ai_authorship_pct,
                churn_score=s.churn_score,
                age_days=s.age_days,
                security_debt_score=s.security_debt_score,
            )
    finally:
        session.close()
    log.info("Persisted %d priority scores for repo %s", len(scores), repository_id)


def run_for_repository(repository_id: str) -> list[PriorityScore]:
    """Full end-to-end: gather inputs, score, persist."""
    inputs = build_priority_inputs_from_rkb(repository_id)
    scores = compute_scores_for_repo(repository_id, inputs)
    persist_scores(repository_id, scores)
    return scores
