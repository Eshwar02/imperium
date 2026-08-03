"""Tests for the map-reduce scale layer over the module hierarchy. No network."""
from __future__ import annotations

from types import SimpleNamespace

from imperium.agents import scale
from imperium.agents.base import AgentContext


def _ctx() -> AgentContext:
    return AgentContext(repository_id="repo-1", repo_path="/tmp/repo")


def _finding_json(title: str, loc: str) -> str:
    return f'[{{"category": "security", "title": "{title}", "detail": "d", "confidence": 0.8, "locations": ["{loc}"]}}]'


def test_map_reduce_aggregates_per_module_and_tags(monkeypatch):
    modules = [SimpleNamespace(name="a", path="mod/a.py"), SimpleNamespace(name="b", path="mod/b.py")]
    monkeypatch.setattr(scale, "_ordered_modules", lambda rid: modules)

    calls: list[str] = []

    def fake_run(role, system, task, ctx):
        calls.append(ctx.scratch.get("module_path"))
        # distinct finding per module
        return _finding_json(f"issue-{ctx.scratch['module_path']}", ctx.scratch["module_path"])

    monkeypatch.setattr("imperium.agents.agent_factory.run_tool_agent", fake_run)

    out = scale.run_scaled_findings(
        "security", "sys", _ctx(), task_for_module=lambda m: f"do {m.path}", whole_repo_task="all"
    )
    assert len(out) == 2
    assert {f["module"] for f in out} == {"mod/a.py", "mod/b.py"}
    assert set(calls) == {"mod/a.py", "mod/b.py"}  # each module bounded its own ctx


def test_falls_back_to_whole_repo_without_modules(monkeypatch):
    monkeypatch.setattr(scale, "_ordered_modules", lambda rid: [])
    monkeypatch.setattr(
        "imperium.agents.agent_factory.run_tool_agent",
        lambda role, system, task, ctx: _finding_json("whole", "x.py:1"),
    )
    out = scale.run_scaled_findings(
        "research", "sys", _ctx(), task_for_module=lambda m: "", whole_repo_task="all"
    )
    assert len(out) == 1
    assert out[0]["title"] == "whole"


def test_dedupe_drops_cross_module_duplicates():
    findings = [
        {"title": "dup", "locations": ["a.py:1"]},
        {"title": "dup", "locations": ["a.py:1"]},
        {"title": "dup", "locations": ["b.py:2"]},
    ]
    assert len(scale._dedupe(findings)) == 2


def test_module_failure_does_not_fail_run(monkeypatch):
    modules = [SimpleNamespace(name="a", path="a.py"), SimpleNamespace(name="b", path="b.py")]
    monkeypatch.setattr(scale, "_ordered_modules", lambda rid: modules)

    def flaky(role, system, task, ctx):
        if ctx.scratch["module_path"] == "a.py":
            raise RuntimeError("provider down for this one")
        return _finding_json("ok", "b.py:3")

    monkeypatch.setattr("imperium.agents.agent_factory.run_tool_agent", flaky)
    out = scale.run_scaled_findings(
        "security", "sys", _ctx(), task_for_module=lambda m: "", whole_repo_task="all"
    )
    assert len(out) == 1 and out[0]["title"] == "ok"
