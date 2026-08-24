"""POST /api/ingest — adding a project.

Regression: ingest used to swallow database-persistence failures and return
HTTP 200, so a project silently never appeared in the rail. It must now surface
a clear error when the repository row cannot be saved.
"""
from fastapi.testclient import TestClient

from imperium.main import app

client = TestClient(app)


def _noop_clone(*args, **kwargs):
    return None


def test_ingest_surfaces_persist_failure(monkeypatch):
    """If the DB is unreachable, /api/ingest must fail loudly, not fake success."""
    import git
    import imperium.rkb.store as store

    monkeypatch.setattr(git.Repo, "clone_from", staticmethod(_noop_clone))

    def _boom():
        raise RuntimeError("tenant/user not found")

    monkeypatch.setattr(store, "get_session", _boom)

    r = client.post("/api/ingest", json={"repo_url": "https://example.com/x.git", "ref": "HEAD"})
    assert r.status_code == 503, r.text
    assert "database" in r.json()["detail"].lower()


def test_ingest_ok_when_persist_succeeds(monkeypatch):
    """Happy path: a successful persist returns 200 with the repository id."""
    import git
    import imperium.rkb.store as store

    monkeypatch.setattr(git.Repo, "clone_from", staticmethod(_noop_clone))

    class _FakeSession:
        def close(self):
            pass

    # load_repository imports get_session/upsert_repository from the store module.
    monkeypatch.setattr(store, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(store, "upsert_repository", lambda *a, **k: None)

    r = client.post("/api/ingest", json={"repo_url": "https://example.com/x.git", "ref": "HEAD"})
    assert r.status_code == 200, r.text
    assert "repository_id" in r.json()
