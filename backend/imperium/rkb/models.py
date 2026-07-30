"""RKB relational schema (TDD §5). SQLAlchemy 2.0 models.

All new tables added per spec §1.1–§1.6:
  - TransformationPriority (§1.1)
  - ChangesetManifest + ChangesetFile (§1.2)
  - TimelineEvent (§1.6)
  - SimulationResult (§1.5)

Decision extended for full HITL audit trail (§1.3).
BusinessRule extended for registry semantics: dedup hash + versioning (§1.4).

Run migrations with Alembic (see alembic/ directory).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    ref: Mapped[str] = mapped_column(String, default="HEAD")
    languages: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    modules: Mapped[list["Module"]] = relationship(back_populates="repository")
    business_rules: Mapped[list["BusinessRule"]] = relationship(back_populates="repository")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="repository")
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(back_populates="repository")
    priorities: Mapped[list["TransformationPriority"]] = relationship(back_populates="repository")
    changesets: Mapped[list["ChangesetManifest"]] = relationship(back_populates="repository")
    simulations: Mapped[list["SimulationResult"]] = relationship(back_populates="repository")


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    name: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_authorship_pct: Mapped[float] = mapped_column(Float, default=0.0)  # TDD §12.3
    comprehension_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, default=False)

    repository: Mapped[Repository] = relationship(back_populates="modules")
    priorities: Mapped[list["TransformationPriority"]] = relationship(back_populates="module")


class BusinessRule(Base):
    """Implicit rule extracted from code (TDD §5, §7). Registry semantics: dedup + version."""
    __tablename__ = "business_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    statement: Mapped[str] = mapped_column(Text)
    # Dedup: canonical hash of normalized statement text
    statement_hash: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)  # latest version flag
    locations: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    verified: Mapped[bool] = mapped_column(default=False)  # human-verified knowledge
    developer_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Links to graph and decisions (stored as ID lists; real FK via join table optional)
    linked_node_ids: Mapped[list] = mapped_column(JSON, default=list)   # Neo4j node IDs
    linked_decision_ids: Mapped[list] = mapped_column(JSON, default=list)
    # HITL: question asked to developer for low-confidence rules
    hitl_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    repository: Mapped[Repository] = relationship(back_populates="business_rules")

    __table_args__ = (
        Index("ix_business_rules_repo_hash", "repository_id", "statement_hash"),
    )


class Decision(Base):
    """Decision log — why a change was made, rule preserved, alternative rejected.

    Extended for full HITL audit trail (§1.3): who approved, timestamp, origin,
    prompt asked, and verdict. Append-only — never overwrite.
    """
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    category: Mapped[str] = mapped_column(String)
    change_summary: Mapped[str] = mapped_column(Text)
    rule_preserved: Mapped[str | None] = mapped_column(Text, nullable=True)
    alternative_rejected: Mapped[str | None] = mapped_column(Text, nullable=True)
    gate: Mapped[str | None] = mapped_column(String, nullable=True)  # gate-a | gate-b

    # HITL extension (§1.3)
    origin: Mapped[str] = mapped_column(String, default="agent")  # agent | human
    approver: Mapped[str | None] = mapped_column(String, nullable=True)  # username / agent name
    approved_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)  # approve | reject | defer
    prompt_asked: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    repository: Mapped[Repository] = relationship(back_populates="decisions")


class TestResult(Base):
    """Baseline vs post-change test outcomes for the behavioral diff (PRD §10)."""
    __tablename__ = "test_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    phase: Mapped[str] = mapped_column(String)  # baseline | post_change
    dimension: Mapped[str] = mapped_column(String)  # security | dataflow | load | perf | behavior
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)


# ── §1.1 Transformation Priority ─────────────────────────────────────────────

class TransformationPriority(Base):
    """Priority score per file/module for the Transformation agent (§1.1)."""
    __tablename__ = "transformation_priority"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    module_id: Mapped[str | None] = mapped_column(ForeignKey("modules.id"), nullable=True)
    file_path: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    # Factor breakdown
    blast_radius_count: Mapped[int] = mapped_column(Integer, default=0)
    business_rule_density: Mapped[float] = mapped_column(Float, default=0.0)
    business_rule_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ai_authorship_pct: Mapped[float] = mapped_column(Float, default=0.0)
    churn_score: Mapped[float] = mapped_column(Float, default=0.0)
    age_days: Mapped[int] = mapped_column(Integer, default=0)
    security_debt_score: Mapped[float] = mapped_column(Float, default=0.0)
    factor_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    repository: Mapped[Repository] = relationship(back_populates="priorities")
    module: Mapped[Module | None] = relationship(back_populates="priorities")


# ── §1.2 Changeset Manifest ───────────────────────────────────────────────────

class ChangesetManifest(Base):
    """Changeset manifest grouping files by module/domain (§1.2)."""
    __tablename__ = "changeset_manifests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | approved | rejected
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    repository: Mapped[Repository] = relationship(back_populates="changesets")
    files: Mapped[list["ChangesetFile"]] = relationship(back_populates="manifest")


class ChangesetFile(Base):
    """Individual file entry within a changeset manifest."""
    __tablename__ = "changeset_files"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    manifest_id: Mapped[str] = mapped_column(ForeignKey("changeset_manifests.id"))
    file_path: Mapped[str] = mapped_column(String)
    cluster_label: Mapped[str | None] = mapped_column(String, nullable=True)  # module/domain group
    call_graph_proximity: Mapped[float] = mapped_column(Float, default=0.0)
    shared_rule_ids: Mapped[list] = mapped_column(JSON, default=list)

    manifest: Mapped[ChangesetManifest] = relationship(back_populates="files")


# ── §1.5 Transformation Simulation ───────────────────────────────────────────

class SimulationResult(Base):
    """Dry-run simulation: old code → new code → diff → confidence (§1.5)."""
    __tablename__ = "simulation_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    file_path: Mapped[str] = mapped_column(String)
    old_code_hash: Mapped[str] = mapped_column(String(64))
    new_code: Mapped[str] = mapped_column(Text)
    diff: Mapped[str] = mapped_column(Text)
    expected_old_behavior: Mapped[str | None] = mapped_column(Text, nullable=True)
    predicted_new_behavior: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    safety_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_vector_ids: Mapped[list] = mapped_column(JSON, default=list)  # Qdrant point IDs
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    repository: Mapped[Repository] = relationship(back_populates="simulations")


# ── §1.6 Repository Timeline ──────────────────────────────────────────────────

class TimelineEvent(Base):
    """A single git-derived event in the repository's history (§1.6)."""
    __tablename__ = "timeline_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    commit_sha: Mapped[str] = mapped_column(String(40))
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    committed_at: Mapped[dt.datetime] = mapped_column(nullable=True)
    event_type: Mapped[str] = mapped_column(String)
    # churn | refactor | dependency_shift | incident_fix | feature | doc | test
    files_changed: Mapped[list] = mapped_column(JSON, default=list)
    modules_affected: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    churn_lines: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    repository: Mapped[Repository] = relationship(back_populates="timeline_events")

    __table_args__ = (
        Index("ix_timeline_repo_sha", "repository_id", "commit_sha"),
        UniqueConstraint("repository_id", "commit_sha", name="uq_timeline_repo_sha"),
    )
