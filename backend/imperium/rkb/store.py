"""Postgres relational store — RKB facade (TDD §5).

Foundation: engine/session factory + lazy schema create + ping. Query helpers
are TODO(team).
"""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from imperium.config import get_settings
from imperium.rkb.models import Base

_settings = get_settings()
_engine = create_engine(_settings.postgres_dsn, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)


def init_schema() -> None:
    """Create tables if absent. TODO(team): replace with Alembic migrations."""
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
