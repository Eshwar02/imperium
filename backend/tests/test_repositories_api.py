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
