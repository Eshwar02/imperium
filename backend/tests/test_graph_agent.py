"""GraphAgent lays out plan steps into a node graph with dashed dependency edges.

No API key in tests → the LLM layout is unavailable, so we exercise the deterministic
linear fallback and the shape guarantees the frontend relies on.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from imperium.agents.graph_agent import GraphAgent
from imperium.main import app

client = TestClient(app)

STEPS = [
    {"file": "models.py", "action": "add field", "rationale": "schema"},
    {"file": "api.py", "action": "use field", "rationale": "expose"},
    {"file": "tests/test_api.py", "action": "cover it", "rationale": "verify"},
]


def test_layout_has_root_and_task_nodes():
    g = GraphAgent().layout(STEPS)
    ids = {n["id"] for n in g["nodes"]}
    assert ids == {"root", "models.py", "api.py", "tests/test_api.py"}
    assert next(n for n in g["nodes"] if n["id"] == "root")["type"] == "root"


def test_contains_edges_from_root_are_dashed():
    g = GraphAgent().layout(STEPS)
    contains = [e for e in g["edges"] if e["kind"] == "contains"]
    assert len(contains) == 3
    assert all(e["style"] == "dashed" and e["source"] == "root" for e in contains)


def test_dependency_edges_are_valid_and_dashed():
    """Deps come from the low-cost LLM when a key is set, else a linear fallback.

    Either way: every dep edge connects two distinct known files and is dashed.
    """
    g = GraphAgent().layout(STEPS)
    files = {"models.py", "api.py", "tests/test_api.py"}
    deps = [e for e in g["edges"] if e["kind"] == "depends"]
    assert deps, "expected at least one dependency edge for a 3-step plan"
    for e in deps:
        assert e["source"] in files and e["target"] in files and e["source"] != e["target"]
        assert e["style"] == "dashed"


def test_dependency_edges_linear_fallback_without_llm(monkeypatch):
    """With the LLM path forced to fail, deps fall back to the plan-order chain."""
    def _boom(*a, **k):
        raise RuntimeError("no provider")

    monkeypatch.setattr("imperium.llm.factory.build_runnable", _boom)
    g = GraphAgent().layout(STEPS)
    deps = [(e["source"], e["target"]) for e in g["edges"] if e["kind"] == "depends"]
    assert deps == [("models.py", "api.py"), ("api.py", "tests/test_api.py")]


def test_empty_and_single_step():
    assert GraphAgent().layout([]) == {"nodes": [{"id": "root", "label": "CodeAgent", "type": "root", "detail": "plan"}], "edges": []}
    g = GraphAgent().layout([{"file": "a.py", "action": "x"}])
    assert [e for e in g["edges"] if e["kind"] == "depends"] == []  # no deps with one node


def test_graph_endpoint_with_supplied_steps():
    resp = client.post("/api/code/r1/graph", json={"instruction": "x", "steps": STEPS})
    assert resp.status_code == 200
    body = resp.json()
    assert {n["id"] for n in body["nodes"]} >= {"root", "models.py"}
    assert any(e["kind"] == "depends" for e in body["edges"])
