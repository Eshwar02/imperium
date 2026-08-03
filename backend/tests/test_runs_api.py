"""HTTP-level tests for run lifecycle + live agent-graph routes.

Drives the run_manager singleton with a stub graph so the routes exercise real
list / graph / delete behaviour without live LLMs or a database.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from imperium.core.graph_orchestrator import build_graph
from imperium.main import app
from tests.test_agent_graph import _StubSteps

client = TestClient(app)


@pytest.fixture
def stub_run():
    """Register + drive one run on the singleton, yield its id, then clean up."""
    from imperium.api.routes.runs import run_manager

    original = run_manager._graph
    run_manager._graph = build_graph(steps=_StubSteps(), checkpointer=InMemorySaver())
    run_id = run_manager.start_run("r1", "/x")
    try:
        yield run_id
    finally:
        run_manager._runs.pop(run_id, None)
        run_manager._graph = original


def test_get_run_graph_returns_nodes_and_edges(stub_run):
    resp = client.get(f"/api/runs/{stub_run}/graph")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == stub_run
    assert {n["id"] for n in body["nodes"]} >= {"run", "analyze", "gate_a"}
    assert any(e["kind"] == "next" for e in body["edges"])
    by_id = {n["id"]: n for n in body["nodes"]}
    assert by_id["gate_a"]["status"] == "awaiting"


def test_list_runs_includes_the_run(stub_run):
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert any(r["run_id"] == stub_run for r in resp.json()["runs"])


def test_delete_run(stub_run):
    assert client.delete(f"/api/runs/{stub_run}").status_code == 200
    # gone: graph + fetch now 404
    assert client.get(f"/api/runs/{stub_run}/graph").status_code == 404
    assert client.get(f"/api/runs/{stub_run}").status_code == 404


def test_graph_and_delete_unknown_run_404():
    assert client.get("/api/runs/nope/graph").status_code == 404
    assert client.delete("/api/runs/nope").status_code == 404
