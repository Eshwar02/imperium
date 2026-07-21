"""RKB relational schema (TDD §5). SQLAlchemy 2.0 models.

Foundation: the core tables the pipeline reads/writes. Extend per team need.
Run migrations with Alembic (TODO(team): alembic init + first revision).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, Float, ForeignKey, String, Text
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


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    name: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_authorship_pct: Mapped[float] = mapped_column(Float, default=0.0)  # TDD §12.3

    repository: Mapped[Repository] = relationship(back_populates="modules")


class BusinessRule(Base):
    """Implicit rule extracted from code (TDD §5, §7). Confidence drives HITL."""
    __tablename__ = "business_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    statement: Mapped[str] = mapped_column(Text)
    locations: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    verified: Mapped[bool] = mapped_column(default=False)  # human-verified knowledge
    developer_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    repository: Mapped[Repository] = relationship(back_populates="business_rules")


class Decision(Base):
    """Decision log — why a change was made, rule preserved, alternative rejected (PRD §11)."""
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    category: Mapped[str] = mapped_column(String)
    change_summary: Mapped[str] = mapped_column(Text)
    rule_preserved: Mapped[str | None] = mapped_column(Text, nullable=True)
    alternative_rejected: Mapped[str | None] = mapped_column(Text, nullable=True)
    gate: Mapped[str | None] = mapped_column(String, nullable=True)  # gate-a | gate-b
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
