"""Tests for the LLM client shim (complete/chat/token accounting).

The runnable is stubbed so nothing hits the network — we only verify message
construction, text extraction, and per-role token accumulation.
"""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from imperium.llm import client


class _FakeRunnable:
    """Stand-in for a built runnable; captures the messages it was invoked with."""

    def __init__(self, reply: str, usage: dict | None = None):
        self.reply = reply
        self.usage = usage
        self.seen: list = []

    def invoke(self, messages):
        self.seen = messages
        return AIMessage(content=self.reply, usage_metadata=self.usage)


@pytest.fixture(autouse=True)
def _reset_usage():
    client.reset_token_usage()
    yield
    client.reset_token_usage()


def test_complete_builds_system_and_user_messages(monkeypatch):
    fake = _FakeRunnable("hello there")
    monkeypatch.setattr(client, "build_runnable", lambda role, temp=0.2: fake)

    out = client.complete("research", "the prompt", system="be terse")

    assert out == "hello there"
    assert fake.seen == [("system", "be terse"), ("user", "the prompt")]


def test_complete_without_system_omits_system_message(monkeypatch):
    fake = _FakeRunnable("ok")
    monkeypatch.setattr(client, "build_runnable", lambda role, temp=0.2: fake)

    client.complete("structure", "just this")

    assert fake.seen == [("user", "just this")]


def test_chat_records_token_usage_per_role(monkeypatch):
    usage = {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20}
    monkeypatch.setattr(
        client, "build_runnable", lambda role, temp=0.2: _FakeRunnable("hi", usage)
    )

    client.chat("documentation", [("user", "a")])
    client.chat("documentation", [("user", "b")])

    snapshot = client.get_token_usage()
    assert snapshot["documentation"] == {
        "input_tokens": 24,
        "output_tokens": 16,
        "total_tokens": 40,
        "calls": 2,
    }


def test_chat_wraps_provider_failure_in_runtimeerror(monkeypatch):
    class _Boom:
        def invoke(self, messages):
            raise ConnectionError("all down")

    monkeypatch.setattr(client, "build_runnable", lambda role, temp=0.2: _Boom())

    with pytest.raises(RuntimeError, match="All providers failed for role 'security'"):
        client.chat("security", [("user", "x")])
