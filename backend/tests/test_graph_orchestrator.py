"""Tests for the durable, gated LangGraph orchestration and the RunManager.

Uses stub Steps + an in-memory checkpointer so the control flow — gate interrupts,
resumption, progress — is exercised without live LLMs or a database.
"""
from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from imperium.core.graph_orchestrator import Steps, build_graph
from imperium.core.runs import RunManager


class _StubSteps(Steps):
    def __init__(self):  # bypass Orchestrator construction
        pass

    def build_kb(self, state):
        return {"parsed_files": 3}

    def analyze(self, state):
        return {
            "structure_map": {"nodes": [{"id": "a"}], "edges": []},
            "findings": [{"category": "security", "title": "x", "detail": "d", "confidence": 0.9}],
        }

    def simulate(self, state):
        return [{"file_path": "a.py", "confidence_score": 0.8, "safety_passed": True}]

    def finalize(self, state):
        return {"architecture": "# Docs"}


@pytest.fixture
def graph():
    return build_graph(steps=_StubSteps(), checkpointer=InMemorySaver())


def _config(tid="run-1"):
    return {"configurable": {"thread_id": tid}}


def test_graph_pauses_at_gate_a(graph):
    graph.invoke({"repository_id": "r1", "repo_path": "/x"}, _config())
    snap = graph.get_state(_config())
    assert snap.next  # paused
    payload = snap.tasks[0].interrupts[0].value
    assert payload["gate"] == "A"
    assert payload["findings"][0]["title"] == "x"


def test_graph_resumes_through_both_gates_to_completion(graph):
    from langgraph.types import Command

    graph.invoke({"repository_id": "r1", "repo_path": "/x"}, _config())
    # Gate A: approve security
    graph.invoke(Command(resume={"security": "approve"}), _config())
    snap = graph.get_state(_config())
    assert snap.tasks[0].interrupts[0].value["gate"] == "B"  # now at gate B
    # Gate B: approve
    graph.invoke(Command(resume={"security": "approve"}), _config())
    final = graph.get_state(_config())
    assert not final.next  # complete
    assert final.values["stage"] == "complete"
    assert final.values["docs"] == {"architecture": "# Docs"}
    assert final.values["approved_categories"] == ["security"]


# ── RunManager ────────────────────────────────────────────────────────────────

def test_run_manager_drives_to_gate_and_resumes():
    mgr = RunManager(graph=build_graph(steps=_StubSteps(), checkpointer=InMemorySaver()))

    run_id = mgr.start_run("r1", "/x")
    run = mgr.get_run(run_id)
    assert run["status"] == "awaiting_gate"
    assert run["pending"]["gate"] == "A"

    mgr.resume_gate(run_id, {"security": "approve"})
    assert mgr.get_run(run_id)["pending"]["gate"] == "B"

    final = mgr.resume_gate(run_id, {"security": "approve"})
    assert final["status"] == "complete"
    assert final["stage"] == "complete"

    events = mgr.get_events(run_id)
    assert any(e.get("event") == "complete" for e in events)
    assert any(e.get("node") == "analyze" for e in events)


def test_run_manager_unknown_run_raises():
    mgr = RunManager(graph=build_graph(steps=_StubSteps(), checkpointer=InMemorySaver()))
    with pytest.raises(KeyError):
        mgr.get_run("nope")
