"""RKB chat endpoint: SSE stream with sources, tokens, and done."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from imperium.api.routes import chat as chat_route
from imperium.main import app

client = TestClient(app)


def _parse_sse(body: str) -> list[dict]:
    return [
        json.loads(line[len("data: ") :])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def test_chat_streams_sources_then_tokens_then_done(monkeypatch):
    monkeypatch.setattr(
        chat_route,
        "_retrieve",
        lambda rid, q, k: [{"score": 0.9, "payload": {"statement": "auth is here", "file": "auth.py"}}],
    )
    import imperium.rkb.embeddings as emb

    monkeypatch.setattr(emb, "count_by_repository", lambda rid: 42)  # repo IS indexed
    # Patch the streaming LLM call to avoid a real provider.
    import imperium.llm.client as llm

    monkeypatch.setattr(llm, "stream", lambda role, msgs, temperature=0.2: iter(["Auth ", "lives in auth.py [1]"]))

    resp = client.post("/api/chat/repo-1", json={"query": "where is auth?"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    assert events[0]["type"] == "sources"
    assert events[0]["sources"][0]["payload"]["file"] == "auth.py"
    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert "".join(tokens) == "Auth lives in auth.py [1]"
    assert events[-1]["type"] == "done"


def test_retrieve_drops_hits_below_threshold(monkeypatch):
    """Weak matches (off-topic queries) must be filtered so we don't feed the LLM noise."""
    import imperium.rkb.embeddings as emb
    from imperium.config import get_settings

    monkeypatch.setattr(
        emb,
        "search",
        lambda q, top_k, filters: [
            {"score": 0.82, "payload": {"text": "real match"}},
            {"score": 0.55, "payload": {"text": "noise"}},
        ],
    )
    thr = get_settings().chat_min_score
    assert thr > 0.55  # sanity: default filters the noise band we observed
    hits = chat_route._retrieve("repo-1", "bearbot", 8)
    assert [h["payload"]["text"] for h in hits] == ["real match"]


def test_chat_no_relevant_context_returns_clean_message(monkeypatch):
    """A real question whose retrieval yields nothing above threshold should get a clean
    one-line reply, not an LLM-generated wall grounded in irrelevant sources."""
    monkeypatch.setattr(chat_route, "_retrieve", lambda rid, q, k: [])
    import imperium.rkb.embeddings as emb

    monkeypatch.setattr(emb, "count_by_repository", lambda rid: 42)  # repo IS indexed

    def _should_not_run(role, msgs, temperature=0.2):
        raise AssertionError("LLM must not be called when there is no relevant context")

    import imperium.llm.client as llm

    monkeypatch.setattr(llm, "stream", _should_not_run)

    resp = client.post("/api/chat/repo-1", json={"query": "tell me about bearbot"})
    events = _parse_sse(resp.text)
    assert events[0] == {"type": "sources", "sources": []}
    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "relevant" in text.lower()
    assert events[-1]["type"] == "done"
    assert "error" not in [e["type"] for e in events]


def test_chat_survives_llm_failure(monkeypatch):
    monkeypatch.setattr(chat_route, "_retrieve", lambda rid, q, k: [])

    def _boom(role, msgs, temperature=0.2):
        raise RuntimeError("no providers")

    import imperium.llm.client as llm

    monkeypatch.setattr(llm, "stream", _boom)

    resp = client.post("/api/chat/repo-1", json={"query": "hi"})
    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types[0] == "sources"
    assert "error" in types
    assert types[-1] == "done"
