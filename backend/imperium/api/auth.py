"""Supabase JWT verification middleware (stateless, RS256 / HS256).

Every request to /api/* must carry:
    Authorization: Bearer <supabase-access-token>

The token is verified against SUPABASE_JWT_SECRET (HS256) from the project
settings.  On success the decoded payload is attached as request.state.user.
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from imperium.config import get_settings

_bearer = HTTPBearer(auto_error=False)


async def verify_jwt(request: Request) -> dict:
    """Dependency — call via Depends(verify_jwt) on any protected router."""
    credentials: HTTPAuthorizationCredentials | None = await _bearer(request)  # type: ignore[arg-type]
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},  # Supabase tokens set aud="authenticated"
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    request.state.user = payload
    return payload
