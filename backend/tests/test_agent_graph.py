"""Tests for the live agent node graph (frontend §7b) + run delete/list.

Uses stub Steps + an in-memory checkpointer so the graph topology, live status
derivation, per-sub-agent events, and lifecycle work without live LLMs or a database.
"""
from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from imperium.core.agent_graph import SUBAGENTS, build_agent_graph
from imperium.core.graph_orchestrator import Steps, build_graph
from imperium.core.run_events import emit, reset_emitter, set_emitter
from imperium.core.runs import RunManager


class _StubSteps(Steps):
    def __init__(self):  # bypass Orchestrator construction
        pass

    def build_kb(self, state):
        return {"parsed_files": 3}

    def analyze(self, state):
        # Emit per-sub-agent progress the way the real Orchestrator does.
        for name, _ in SUBAGENTS:
            emit({"event": "agent_start", "agent": name})
            emit({"event": "agent_done", "agent": name, "findings": 1})
        return {
            "structure_map": {"nodes": [{"id": "a"}], "edges": []},
            "findings": [{"category": "security", "title": "x", "detail": "d", "confidence": 0.9}],
        }

    def simulate(self, state):
        return [{"file_path": "a.py", "confidence_score": 0.8, "safety_passed": True}]

    def finalize(self, state):
        return {"architecture": "# Docs"}


def _mgr():
    return RunManager(graph=build_graph(steps=_StubSteps(), checkpointer=InMemorySaver()))


# ── graph shape ─────────────────────────────────────────────────────────────────

def test_graph_topology_from_empty_run():
    graph = build_agent_graph([], {"run_id": "r", "status": "running", "stage": "build_kb"})
    ids = {n["id"] for n in graph["nodes"]}
    assert "run" in ids
    assert {"build_kb", "analyze", "gate_a", "simulate", "gate_b", "finalize"} <= ids
    assert all(f"analyze.{a}" in ids for a, _ in SUBAGENTS)
    # analyze fans out to every sub-agent
    contains = {(e["source"], e["target"]) for e in graph["edges"] if e["kind"] == "contains"}
    for a, _ in SUBAGENTS:
        assert ("analyze", f"analyze.{a}") in contains


def test_first_stage_is_active_when_running():
    graph = build_agent_graph([], {"run_id": "r", "status": "running", "stage": "build_kb"})
    by_id = {n["id"]: n for n in graph["nodes"]}
    assert by_id["build_kb"]["status"] == "active"
    assert by_id["analyze"]["status"] == "idle"


# ── live status through a real driven run ────────────────────────────────────────

def test_agent_graph_at_gate_a_shows_subagents_done_and_gate_awaiting():
    mgr = _mgr()
    run_id = mgr.start_run("r1", "/x")
    assert mgr.get_run(run_id)["status"] == "awaiting_gate"

    graph = mgr.agent_graph(run_id)
    by_id = {n["id"]: n for n in graph["nodes"]}

    assert by_id["build_kb"]["status"] == "done"
    assert by_id["analyze"]["status"] == "done"
    # per-sub-agent events were captured live and settled green
    for a, _ in SUBAGENTS:
        assert by_id[f"analyze.{a}"]["status"] == "done"
    # paused on Gate A
    assert by_id["gate_a"]["status"] == "awaiting"
    assert by_id["run"]["status"] == "awaiting"


def test_agent_graph_settles_done_on_completion():
    mgr = _mgr()
    run_id = mgr.start_run("r1", "/x")
    mgr.resume_gate(run_id, {"security": "approve"})  # past Gate A
    mgr.resume_gate(run_id, {"security": "approve"})  # past Gate B → complete

    graph = mgr.agent_graph(run_id)
    by_id = {n["id"]: n for n in graph["nodes"]}
    assert mgr.get_run(run_id)["status"] == "complete"
    for stage in ("build_kb", "analyze", "gate_a", "simulate", "gate_b", "finalize"):
        assert by_id[stage]["status"] == "done"
    assert by_id["run"]["status"] == "done"


# ── lifecycle: list + delete ─────────────────────────────────────────────────────

def test_list_and_delete_run():
    mgr = _mgr()
    run_id = mgr.start_run("r1", "/x")
    assert any(r["run_id"] == run_id for r in mgr.list_runs())

    mgr.delete(run_id)
    assert all(r["run_id"] != run_id for r in mgr.list_runs())
    try:
        mgr.agent_graph(run_id)
        assert False, "expected KeyError after delete"
    except KeyError:
        pass


# ── emitter is scoped and safe ───────────────────────────────────────────────────

def test_emit_is_noop_without_active_run():
    # No emitter bound → must not raise.
    emit({"event": "agent_start", "agent": "security"})


def test_emitter_binds_and_resets():
    seen: list[dict] = []
    token = set_emitter(seen.append)
    try:
        emit({"event": "agent_done", "agent": "structure"})
    finally:
        reset_emitter(token)
    assert seen == [{"event": "agent_done", "agent": "structure"}]
    # after reset, emit is a no-op again
    emit({"event": "agent_done", "agent": "security"})
    assert len(seen) == 1
