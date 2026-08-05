"""Supabase JWT verification middleware (stateless).

Every request to /api/* must carry:
    Authorization: Bearer <supabase-access-token>

Supabase projects sign user access tokens with either:
  * an asymmetric JWT signing key (ES256 / RS256), verified against the
    project JWKS at {SUPABASE_URL}/auth/v1/.well-known/jwks.json, or
  * the legacy shared secret (HS256), verified against SUPABASE_JWT_SECRET.

We support both: the token header's `alg` selects the path. On success the
decoded payload is attached as request.state.user.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from imperium.config import get_settings

_bearer = HTTPBearer(auto_error=False)

# --- JWKS cache (asymmetric signing keys) ------------------------------------
_JWKS_TTL = 3600  # seconds; Supabase rotates rarely, refresh hourly
_jwks_lock = threading.Lock()
_jwks_cache: dict[str, object] = {"keys": {}, "fetched_at": 0.0}


def _jwks_url() -> str:
    return get_settings().supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"


def _fetch_jwks() -> dict[str, dict]:
    """Return {kid: jwk} from the project JWKS endpoint."""
    with urllib.request.urlopen(_jwks_url(), timeout=5) as resp:  # noqa: S310 (trusted URL)
        data = json.loads(resp.read())
    return {k["kid"]: k for k in data.get("keys", []) if "kid" in k}


def _get_jwk(kid: str, *, allow_refresh: bool = True) -> dict | None:
    """Look up a JWK by kid, refreshing the cache on miss or expiry."""
    now = time.time()
    with _jwks_lock:
        keys: dict = _jwks_cache["keys"]  # type: ignore[assignment]
        fresh = (now - float(_jwks_cache["fetched_at"])) < _JWKS_TTL  # type: ignore[arg-type]
        if kid in keys and fresh:
            return keys[kid]
        # Cache miss or stale — refetch (handles key rotation).
        if allow_refresh:
            try:
                keys = _fetch_jwks()
                _jwks_cache["keys"] = keys
                _jwks_cache["fetched_at"] = now
            except Exception:  # network/parse error — fall back to stale cache
                keys = _jwks_cache["keys"]  # type: ignore[assignment]
        return keys.get(kid)


async def verify_jwt(request: Request) -> dict:
    """Dependency — call via Depends(verify_jwt) on any protected router."""
    credentials: HTTPAuthorizationCredentials | None = await _bearer(request)  # type: ignore[arg-type]
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Malformed token: {exc}") from exc

    alg = header.get("alg", "")
    settings = get_settings()

    try:
        if alg.startswith(("ES", "RS", "PS", "ED")):
            kid = header.get("kid", "")
            jwk = _get_jwk(kid)
            if jwk is None:
                raise HTTPException(status_code=401, detail="Unknown signing key (kid)")
            payload = jwt.decode(
                token,
                jwk,
                algorithms=[alg],
                options={"verify_aud": False},  # Supabase tokens set aud="authenticated"
            )
        else:  # legacy HS256 shared secret
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    request.state.user = payload
    return payload


def get_user_id(request: Request) -> str | None:
    """Return the authenticated Supabase user id (JWT `sub`), or None.

    Use in routes to owner-scope RKB rows: repositories.owner_id = get_user_id(request).
    """
    user = getattr(request.state, "user", None)
    return user.get("sub") if isinstance(user, dict) else None
