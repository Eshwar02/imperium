"""The insights read-APIs must respond with safe empty payloads even when the backing
stores are down (self-healing degradation), so the frontend never hits a dead route.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from imperium.main import app

client = TestClient(app)


@pytest.mark.parametrize(
    "path, key",
    [
        ("/api/graph/r1", "nodes"),
        ("/api/graph/r1?layer=api", "nodes"),
        ("/api/graph/r1/blast/some:node", "dependents"),
        ("/api/hierarchy/r1", "modules"),
        ("/api/business-rules/r1", "rules"),
        ("/api/priorities/r1", "priorities"),
        ("/api/changesets/r1", "changesets"),
        ("/api/simulations/r1", "simulations"),
        ("/api/timeline/r1", "events"),
        ("/api/usage", "usage"),
    ],
)
def test_insights_routes_respond_safely(path, key):
    resp = client.get(path)
    assert resp.status_code == 200
    assert key in resp.json()


def test_graph_layer_param_maps_to_relations():
    # unknown layer falls back to full graph, still a valid shape
    resp = client.get("/api/graph/r1?layer=nonsense")
    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body and "edges" in body
