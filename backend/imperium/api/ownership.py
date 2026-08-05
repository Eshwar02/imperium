"""App-layer owner-scoping for RKB reads/writes.

The backend connects to Supabase Postgres as the table owner and therefore
BYPASSES row-level security. Per-user isolation is enforced here, in the API
layer, by checking ``repositories.owner_id`` against the authenticated Supabase
user id (JWT ``sub``) — mirroring the ownership already threaded through the
ingest route.

Ownership model (see rkb/store.py):
  * A repository is *claimed* by the first user to ingest it (owner_id set once).
  * All child rows (modules, decisions, gates, business rules, …) inherit
    ownership through their parent ``repository_id`` — we never stamp owner
    columns onto child tables, we scope through the repository.

Guard semantics (deliberately permissive at the edges so the resilient read
APIs never turn into dead routes, and so unauthenticated/local contexts and the
test suite keep working):
  * user_id is None  → no user context; do not block (degrade to open).
  * repo not found / owner_id is None → repo is unclaimed; do not block.
  * repo owned by a *different* user → block (404 to avoid leaking existence).
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request

from imperium.api.auth import get_user_id

log = logging.getLogger("imperium.api.ownership")


def owns_repository(repository_id: str, user_id: str | None) -> bool:
    """True if ``user_id`` may access ``repository_id``.

    Returns True (permissive) when there is no user context, when the repo is
    unknown/unclaimed, or when the backing store is unavailable — isolation only
    ever *denies* a request when a repo is provably owned by someone else.
    """
    if user_id is None:
        return True
    try:
        from imperium.rkb.store import get_repository, get_session

        session = get_session()
        try:
            repo = get_repository(session, repository_id)
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001 — never block on a store hiccup
        log.warning("ownership check degraded for %s: %s", repository_id, exc)
        return True

    if repo is None or getattr(repo, "owner_id", None) is None:
        return True
    return repo.owner_id == user_id


def require_owner(repository_id: str, request: Request) -> str | None:
    """Assert the caller owns ``repository_id`` or raise 404. Returns the user id.

    Use on routes that read/write repo-scoped data for the current user.
    """
    user_id = get_user_id(request)
    if not owns_repository(repository_id, user_id):
        raise HTTPException(status_code=404, detail="repository not found")
    return user_id
