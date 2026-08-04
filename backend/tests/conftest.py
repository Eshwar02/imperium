"""Shared test fixtures.

The API now guards every ``/api/*`` route with a Supabase JWT dependency
(``imperium.api.auth.verify_jwt``). Tests exercise the routes directly via
``TestClient`` without minting real Supabase tokens, so we override the
dependency with a stub authenticated user for the whole test session. This
keeps production auth wiring intact while letting the suite run unauthenticated.
"""
from __future__ import annotations

import pytest

from imperium.api.auth import verify_jwt
from imperium.main import app


def _fake_user() -> dict:
    return {"sub": "test-user", "email": "test@example.com", "role": "authenticated"}


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[verify_jwt] = _fake_user
    yield
    app.dependency_overrides.pop(verify_jwt, None)
