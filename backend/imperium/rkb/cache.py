"""Redis cache — hot context + run coordination (TDD §10)."""
from __future__ import annotations

from functools import lru_cache

from imperium.config import get_settings


@lru_cache
def _client():
    import redis

    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def ping() -> dict[str, str]:
    try:
        _client().ping()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "error": str(exc)[:200]}
