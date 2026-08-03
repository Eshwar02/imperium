"""Postgres relational store — RKB facade (TDD §5).

Engine/session factory + query helpers for all tables.
"""
from __future__ import annotations

import datetime as dt
import hashlib

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from imperium.config import get_settings
from imperium.rkb.models import (
    Base,
    BusinessRule,
    ChangesetFile,
    ChangesetManifest,
    Decision,
    Module,
    Repository,
    SimulationResult,
    TimelineEvent,
    TransformationPriority,
)

_settings = get_settings()

# Supabase requires SSL. psycopg3 honours ?sslmode=require in the DSN directly,
# but we also pass connect_args as a belt-and-suspenders measure.
_engine = create_engine(
    _settings.postgres_dsn,
    future=True,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"} if "supabase.com" in _settings.postgres_dsn else {},
)
SessionLocal = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)


def init_schema() -> None:
    """Bootstrap tables in dev/test environments only.

    Production deployments must use Alembic:
        alembic upgrade head

    This function is intentionally kept for local dev convenience (e.g. running
    tests without a full migration stack), but should not be called in production.
    Guard: skips silently in non-dev environments.
    """
    from imperium.config import get_settings

    if get_settings().imperium_env not in ("dev", "test"):
        import logging
        logging.getLogger("imperium.rkb.store").warning(
            "init_schema() called in env=%s — skipping (use `alembic upgrade head`)",
            get_settings().imperium_env,
        )
        return
    Base.metadata.create_all(_engine)


def get_session() -> Session:
    return SessionLocal()


def ping() -> dict[str, str]:
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001 — health check must not raise
        return {"status": "down", "error": str(exc)[:200]}


# ── Repository helpers ────────────────────────────────────────────────────────

def upsert_repository(session: Session, repo_id: str, url: str | None, ref: str, languages: list[str]) -> Repository:
    obj = session.get(Repository, repo_id)
    if obj is None:
        obj = Repository(id=repo_id, url=url, ref=ref, languages=languages)
        session.add(obj)
    else:
        obj.url = url
        obj.ref = ref
        obj.languages = languages
    session.commit()
    return obj


def get_repository(session: Session, repo_id: str) -> Repository | None:
    return session.get(Repository, repo_id)


# ── Module helpers ────────────────────────────────────────────────────────────

def upsert_module(
    session: Session,
    repository_id: str,
    name: str,
    path: str,
    summary: str | None = None,
    ai_authorship_pct: float = 0.0,
) -> Module:
    obj = session.query(Module).filter_by(repository_id=repository_id, path=path).first()
    if obj is None:
        obj = Module(
            repository_id=repository_id,
            name=name,
            path=path,
            summary=summary,
            ai_authorship_pct=ai_authorship_pct,
        )
        session.add(obj)
    else:
        obj.name = name
        obj.summary = summary
        obj.ai_authorship_pct = ai_authorship_pct
    session.commit()
    return obj


def get_modules(session: Session, repository_id: str) -> list[Module]:
    return session.query(Module).filter_by(repository_id=repository_id).all()


# ── BusinessRule registry helpers ─────────────────────────────────────────────

def _rule_hash(statement: str) -> str:
    return hashlib.sha256(statement.strip().lower().encode()).hexdigest()[:64]


def upsert_business_rule(
    session: Session,
    repository_id: str,
    statement: str,
    locations: list,
    confidence: float,
    hitl_question: str | None = None,
    linked_node_ids: list | None = None,
    linked_decision_ids: list | None = None,
) -> BusinessRule:
    """Dedup by statement hash — if same rule exists update confidence/locations;
    otherwise create a new versioned entry.

    linked_node_ids: Neo4j node IDs for code locations that embody this rule.
    linked_decision_ids: Decision IDs that reference this rule.
    """
    h = _rule_hash(statement)
    existing = (
        session.query(BusinessRule)
        .filter_by(repository_id=repository_id, statement_hash=h, is_current=True)
        .first()
    )
    if existing:
        existing.locations = locations
        existing.confidence = confidence
        if hitl_question:
            existing.hitl_question = hitl_question
        if linked_node_ids is not None:
            # Merge without duplicates
            current = existing.linked_node_ids or []
            existing.linked_node_ids = list(set(current) | set(linked_node_ids))
        if linked_decision_ids is not None:
            current = existing.linked_decision_ids or []
            existing.linked_decision_ids = list(set(current) | set(linked_decision_ids))
        session.commit()
        # Embed updated rule text in Qdrant (idempotent — same hash → same point_id)
        _embed_rule(existing)
        return existing

    obj = BusinessRule(
        repository_id=repository_id,
        statement=statement,
        statement_hash=h,
        locations=locations,
        confidence=confidence,
        hitl_question=hitl_question,
        linked_node_ids=linked_node_ids or [],
        linked_decision_ids=linked_decision_ids or [],
    )
    session.add(obj)
    session.commit()
    # Embed rule text in Qdrant
    _embed_rule(obj)
    return obj


def _embed_rule(rule: BusinessRule) -> None:
    """Embed the rule's statement text into Qdrant for semantic search."""
    try:
        from imperium.rkb.embeddings import upsert as qdrant_upsert

        qdrant_upsert(
            texts=[rule.statement],
            payloads=[{
                "repository_id": rule.repository_id,
                "level": "business_rule",
                "rule_id": rule.id,
                "statement_hash": rule.statement_hash,
                "confidence": rule.confidence,
                "verified": rule.verified,
            }],
        )
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("imperium.rkb.store").warning(
            "Rule embedding failed for %s: %s", rule.id, exc
        )


def link_rule_to_decision(session: Session, rule_id: str, decision_id: str) -> None:
    """Append decision_id to a BusinessRule's linked_decision_ids (§1.4)."""
    obj = session.get(BusinessRule, rule_id)
    if obj:
        current = obj.linked_decision_ids or []
        if decision_id not in current:
            obj.linked_decision_ids = current + [decision_id]
            session.commit()


def link_rule_to_node(session: Session, rule_id: str, node_id: str) -> None:
    """Append a Neo4j node_id to a BusinessRule's linked_node_ids (§1.4)."""
    obj = session.get(BusinessRule, rule_id)
    if obj:
        current = obj.linked_node_ids or []
        if node_id not in current:
            obj.linked_node_ids = current + [node_id]
            session.commit()


def get_unverified_rules(session: Session, repository_id: str, threshold: float = 0.7) -> list[BusinessRule]:
    """Return rules below confidence threshold that need HITL clarification."""
    return (
        session.query(BusinessRule)
        .filter(
            BusinessRule.repository_id == repository_id,
            BusinessRule.confidence < threshold,
            BusinessRule.verified.is_(False),
            BusinessRule.is_current.is_(True),
        )
        .all()
    )


def verify_business_rule(session: Session, rule_id: str, answer: str) -> BusinessRule | None:
    obj = session.get(BusinessRule, rule_id)
    if obj:
        obj.verified = True
        obj.developer_answer = answer
        session.commit()
    return obj


def get_business_rules(session: Session, repository_id: str) -> list[BusinessRule]:
    return (
        session.query(BusinessRule)
        .filter_by(repository_id=repository_id, is_current=True)
        .all()
    )


# ── Decision helpers ──────────────────────────────────────────────────────────

def append_decision(
    session: Session,
    repository_id: str,
    category: str,
    change_summary: str,
    rule_preserved: str | None = None,
    alternative_rejected: str | None = None,
    gate: str | None = None,
    origin: str = "agent",
    approver: str | None = None,
    verdict: str | None = None,
    prompt_asked: str | None = None,
    prompt_answer: str | None = None,
) -> Decision:
    """Append-only — never overwrites existing decisions."""
    obj = Decision(
        repository_id=repository_id,
        category=category,
        change_summary=change_summary,
        rule_preserved=rule_preserved,
        alternative_rejected=alternative_rejected,
        gate=gate,
        origin=origin,
        approver=approver,
        approved_at=dt.datetime.utcnow() if approver else None,
        verdict=verdict,
        prompt_asked=prompt_asked,
        prompt_answer=prompt_answer,
    )
    session.add(obj)
    session.commit()
    return obj


def get_decisions(session: Session, repository_id: str) -> list[Decision]:
    return (
        session.query(Decision)
        .filter_by(repository_id=repository_id)
        .order_by(Decision.created_at)
        .all()
    )


# ── TransformationPriority helpers ────────────────────────────────────────────

def upsert_priority(
    session: Session,
    repository_id: str,
    file_path: str,
    score: float,
    factor_breakdown: dict,
    module_id: str | None = None,
    **kwargs,
) -> TransformationPriority:
    obj = (
        session.query(TransformationPriority)
        .filter_by(repository_id=repository_id, file_path=file_path)
        .first()
    )
    if obj is None:
        obj = TransformationPriority(
            repository_id=repository_id,
            module_id=module_id,
            file_path=file_path,
            score=score,
            factor_breakdown=factor_breakdown,
            **kwargs,
        )
        session.add(obj)
    else:
        obj.score = score
        obj.factor_breakdown = factor_breakdown
        obj.computed_at = dt.datetime.utcnow()
        for k, v in kwargs.items():
            setattr(obj, k, v)
    session.commit()
    return obj


def get_priorities(session: Session, repository_id: str, limit: int = 50) -> list[TransformationPriority]:
    return (
        session.query(TransformationPriority)
        .filter_by(repository_id=repository_id)
        .order_by(TransformationPriority.score.desc())
        .limit(limit)
        .all()
    )


# ── ChangesetManifest helpers ─────────────────────────────────────────────────

def create_changeset(
    session: Session,
    repository_id: str,
    name: str,
    files: list[dict],
    description: str | None = None,
) -> ChangesetManifest:
    manifest = ChangesetManifest(
        repository_id=repository_id,
        name=name,
        description=description,
    )
    session.add(manifest)
    session.flush()  # get manifest.id before inserting files

    for f in files:
        cf = ChangesetFile(
            manifest_id=manifest.id,
            file_path=f["file_path"],
            cluster_label=f.get("cluster_label"),
            call_graph_proximity=f.get("call_graph_proximity", 0.0),
            shared_rule_ids=f.get("shared_rule_ids", []),
        )
        session.add(cf)

    session.commit()
    return manifest


def get_changeset(session: Session, manifest_id: str) -> ChangesetManifest | None:
    return session.get(ChangesetManifest, manifest_id)


def get_changesets(session: Session, repository_id: str) -> list[ChangesetManifest]:
    return session.query(ChangesetManifest).filter_by(repository_id=repository_id).all()


# ── SimulationResult helpers ──────────────────────────────────────────────────

def save_simulation(
    session: Session,
    repository_id: str,
    file_path: str,
    old_code: str,
    new_code: str,
    diff: str,
    confidence_score: float,
    safety_passed: bool,
    expected_old_behavior: str | None = None,
    predicted_new_behavior: str | None = None,
    block_reason: str | None = None,
    evidence_vector_ids: list | None = None,
) -> SimulationResult:
    old_hash = hashlib.sha256(old_code.encode()).hexdigest()[:64]
    obj = SimulationResult(
        repository_id=repository_id,
        file_path=file_path,
        old_code_hash=old_hash,
        new_code=new_code,
        diff=diff,
        expected_old_behavior=expected_old_behavior,
        predicted_new_behavior=predicted_new_behavior,
        confidence_score=confidence_score,
        safety_passed=safety_passed,
        blocked=not safety_passed,
        block_reason=block_reason,
        evidence_vector_ids=evidence_vector_ids or [],
    )
    session.add(obj)
    session.commit()
    return obj


def get_simulations(session: Session, repository_id: str) -> list[SimulationResult]:
    return session.query(SimulationResult).filter_by(repository_id=repository_id).all()


# ── TimelineEvent helpers ─────────────────────────────────────────────────────

def upsert_timeline_event(
    session: Session,
    repository_id: str,
    commit_sha: str,
    author: str | None,
    committed_at: dt.datetime | None,
    event_type: str,
    files_changed: list,
    modules_affected: list,
    summary: str | None,
    churn_lines: int,
) -> TimelineEvent:
    obj = (
        session.query(TimelineEvent)
        .filter_by(repository_id=repository_id, commit_sha=commit_sha)
        .first()
    )
    if obj is not None:
        return obj  # idempotent — timeline is append-only per commit

    obj = TimelineEvent(
        repository_id=repository_id,
        commit_sha=commit_sha,
        author=author,
        committed_at=committed_at,
        event_type=event_type,
        files_changed=files_changed,
        modules_affected=modules_affected,
        summary=summary,
        churn_lines=churn_lines,
    )
    session.add(obj)
    session.commit()
    return obj


def get_timeline(session: Session, repository_id: str) -> list[TimelineEvent]:
    return (
        session.query(TimelineEvent)
        .filter_by(repository_id=repository_id)
        .order_by(TimelineEvent.committed_at)
        .all()
    )
