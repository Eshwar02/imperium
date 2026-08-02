"""Analysis endpoints: background run + snapshot retrieval."""
from __future__ import annotations

from fastapi.testclient import TestClient

from imperium.api.schemas import AnalysisResponse, Category, Finding
from imperium.core import orchestrator
from imperium.main import app

client = TestClient(app)


def test_post_analysis_runs_in_background_and_returns_running(monkeypatch):
    calls: list[str] = []

    def _fake_bg(self, repository_id: str) -> None:  # noqa: ANN001
        calls.append(repository_id)

    monkeypatch.setattr(orchestrator.Orchestrator, "analyze_in_background", _fake_bg)

    resp = client.post("/api/analysis/repo-1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    # BackgroundTasks run after the response is sent by TestClient.
    assert calls == ["repo-1"]


def test_get_analysis_returns_cached_snapshot():
    snapshot = AnalysisResponse(
        repository_id="repo-2",
        status="complete",
        findings=[Finding(category=Category.security, title="X", detail="d", confidence=0.9)],
    )
    orchestrator._ANALYSIS_SNAPSHOTS["repo-2"] = snapshot
    try:
        resp = client.get("/api/analysis/repo-2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "complete"
        assert body["findings"][0]["title"] == "X"
    finally:
        orchestrator._ANALYSIS_SNAPSHOTS.pop("repo-2", None)


def test_get_analysis_reports_running_state():
    orchestrator._ANALYSIS_RUNNING.add("repo-3")
    try:
        resp = client.get("/api/analysis/repo-3")
        assert resp.json()["status"] == "running"
    finally:
        orchestrator._ANALYSIS_RUNNING.discard("repo-3")
