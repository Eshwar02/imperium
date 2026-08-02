"""Comprehension endpoints: checks + per-module scores, and answer recording."""
from __future__ import annotations

from fastapi.testclient import TestClient

from imperium.api.routes import comprehension as comp_route
from imperium.main import app

client = TestClient(app)


class _FakeModule:
    def __init__(self, path, ai_pct=80.0, score=None, flagged=True):
        self.name = path.split("/")[-1]
        self.path = path
        self.ai_authorship_pct = ai_pct
        self.comprehension_score = score
        self.flagged_for_review = flagged


class _FakeSession:
    def __init__(self, modules):
        self._modules = modules
        self.committed = False

    def commit(self):
        self.committed = True

    def close(self):
        pass


def test_get_comprehension_returns_checks_and_modules(monkeypatch):
    mods = [_FakeModule("app/auth.py", score=0.3)]
    monkeypatch.setattr(
        comp_route.ComprehensionAgent, "run", lambda self, ctx: {"checks": [{"decision_id": "d1"}]}
    )
    import imperium.rkb.store as store

    monkeypatch.setattr(store, "get_session", lambda: _FakeSession(mods))
    monkeypatch.setattr(store, "get_modules", lambda session, rid: session._modules)

    resp = client.get("/api/comprehension/repo-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["checks"][0]["decision_id"] == "d1"
    assert body["modules"][0]["path"] == "app/auth.py"


def test_answer_records_score_and_unflags(monkeypatch):
    mod = _FakeModule("app/auth.py", score=None, flagged=True)
    session = _FakeSession([mod])
    import imperium.rkb.store as store

    monkeypatch.setattr(store, "get_session", lambda: session)
    monkeypatch.setattr(store, "get_modules", lambda s, rid: s._modules)

    resp = client.post(
        "/api/comprehension/repo-1/answer",
        json={"module_path": "app/auth.py", "comprehension_score": 0.8},
    )
    body = resp.json()
    assert body["recorded"] is True
    assert body["comprehension_score"] == 0.8
    assert body["flagged_for_review"] is False
    assert mod.comprehension_score == 0.8
    assert session.committed is True


def test_answer_unknown_module(monkeypatch):
    session = _FakeSession([])
    import imperium.rkb.store as store

    monkeypatch.setattr(store, "get_session", lambda: session)
    monkeypatch.setattr(store, "get_modules", lambda s, rid: [])

    resp = client.post(
        "/api/comprehension/repo-1/answer",
        json={"module_path": "nope.py", "comprehension_score": 0.9},
    )
    assert resp.json()["recorded"] is False
