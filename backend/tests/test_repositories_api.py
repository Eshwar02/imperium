"""GET /api/repositories — owner-scoped repository list for the UI rail."""
from fastapi.testclient import TestClient

from imperium.main import app

client = TestClient(app)


def test_list_repositories_ok():
    r = client.get("/api/repositories")
    assert r.status_code == 200
    body = r.json()
    assert "repositories" in body
    assert isinstance(body["repositories"], list)


def test_list_repositories_degrades_without_db(monkeypatch):
    """No live Postgres (as in CI) must yield an empty list, not a 500."""
    import imperium.rkb.store as store

    def _boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(store, "get_session", _boom)

    r = client.get("/api/repositories")
    assert r.status_code == 200
    assert r.json() == {"repositories": []}
