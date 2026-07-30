"""Tests for the self-healing layer: diagnosis, remediation, silent degradation."""
from __future__ import annotations

import pytest

from imperium.core import healing
from imperium.core.healing import RecoveryAction, classify_error, heal_call, self_healing


@pytest.mark.parametrize(
    "exc, expected",
    [
        (ConnectionError("connection refused"), RecoveryAction.RECONNECT),
        (TimeoutError("timed out"), RecoveryAction.RETRY),
        (RuntimeError("429 rate limit exceeded"), RecoveryAction.SWITCH_PROVIDER),
        (RuntimeError("maximum context length reached"), RecoveryAction.REDUCE_SCOPE),
        (ValueError("bad json"), RecoveryAction.SKIP),
    ],
)
def test_classify_error(exc, expected):
    assert classify_error(exc) == expected


def test_heal_call_retries_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("connection dropped")  # RECONNECT → recoverable
        return "ok"

    assert heal_call("test.flaky", flaky, retries=3) == "ok"
    assert calls["n"] == 3


def test_heal_call_skips_unrecoverable_and_returns_default():
    def bad():
        raise ValueError("unparseable")  # SKIP → no retry

    calls = {"n": 0}

    def counting_bad():
        calls["n"] += 1
        return bad()

    assert heal_call("test.bad", counting_bad, default=[]) == []
    assert calls["n"] == 1  # skipped immediately, not retried


def test_heal_call_gives_up_after_retries_silently():
    def always_down():
        raise ConnectionError("still down")

    # Never raises — returns the default after exhausting retries.
    assert heal_call("test.down", always_down, retries=2, default="degraded") == "degraded"


def test_self_healing_decorator_returns_default():
    @self_healing("test.decorated", default={"findings": []})
    def run():
        raise KeyError("boom")  # SKIP

    assert run() == {"findings": []}


def test_incidents_are_recorded_silently():
    before = len(healing.get_incidents(500))
    heal_call("test.record", lambda: (_ for _ in ()).throw(ValueError("x")), default=None)
    after = healing.get_incidents(500)
    assert len(after) > before
    assert after[-1]["component"] == "test.record"
    assert after[-1]["action"] == "skip"


def test_healing_agent_falls_back_without_llm():
    # ConnectionError is unambiguous → deterministic, no LLM consulted.
    action = healing.healing_agent.diagnose(ConnectionError("refused"), {"component": "x"})
    assert action == RecoveryAction.RECONNECT
