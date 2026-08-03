"""Tests for the sandbox runner output parsing and Testing agent verification.
No Docker, no DB — the sandbox call and persistence are stubbed.
"""
from __future__ import annotations

import pytest

from imperium.agents.base import AgentContext


@pytest.mark.parametrize(
    "text, expected",
    [
        ("=== 3 passed, 1 failed in 0.2s ===", (3, 1)),
        ("Tests: 1 failed, 3 passed", (3, 1)),
        ("5 passed", (5, 0)),
        ("2 errors, 1 passed", (1, 2)),
        ("no counts here", (0, 0)),
    ],
)
def test_parse_test_output(text, expected):
    from imperium.sandbox.runner import parse_test_output

    assert parse_test_output(text) == expected


def test_sandbox_run_degrades_without_docker(monkeypatch):
    from imperium.sandbox import runner

    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    result = runner.run("/tmp/x", "pytest", "baseline")
    assert result.exit_code == -1
    assert "docker" in result.stderr.lower()


def test_run_verification_executes_both_phases(monkeypatch):
    from imperium.agents.testing import TestingAgent
    from imperium.sandbox.runner import SandboxResult

    seen_phases = []

    def fake_run(path, cmd, phase):
        seen_phases.append(phase)
        return SandboxResult(exit_code=0, passed=4, failed=0)

    monkeypatch.setattr("imperium.sandbox.runner.run", fake_run)
    # persistence is best-effort; stub the store getter so no DB is touched
    monkeypatch.setattr(TestingAgent, "_persist_result", lambda *a, **k: None)

    ctx = AgentContext(repository_id="r1", repo_path="/tmp/repo")
    out = TestingAgent().run_verification(ctx, test_command="pytest -q")
    assert set(seen_phases) == {"baseline", "post_change"}
    assert out["phases"]["baseline"]["passed"] is True
    assert out["phases"]["baseline"]["pass_count"] == 4
