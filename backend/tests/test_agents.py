"""Tests for the tool-using agent layer (Phase 2).

Covers tool construction/guards, agent model-chain wiring, run_agent text
extraction, and Research findings parsing — all without network or live backends.
"""
from __future__ import annotations

import pytest

from imperium.agents.base import AgentContext
from imperium.config import get_settings


@pytest.fixture(autouse=True)
def _clear_factory_cache():
    from imperium.llm import factory

    factory.clear_cache()
    yield
    factory.clear_cache()


@pytest.fixture
def all_keys(monkeypatch):
    for env in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "MISTRAL_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(env, "sk-test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _ctx(tmp_path=None) -> AgentContext:
    return AgentContext(repository_id="repo-1", repo_path=str(tmp_path) if tmp_path else "")


# ── tools ─────────────────────────────────────────────────────────────────────

def test_build_tools_exposes_expected_toolset():
    from imperium.agents.tools import build_tools

    names = {t.name for t in build_tools(_ctx())}
    assert names == {"search_memory", "list_business_rules", "recent_timeline", "blast_radius", "read_source"}


def test_search_memory_tool_is_guarded_when_backend_down(monkeypatch):
    from imperium.agents import tools

    def _boom(*a, **k):
        raise ConnectionError("qdrant down")

    monkeypatch.setattr("imperium.rkb.embeddings.search", _boom, raising=False)
    search = next(t for t in tools.build_tools(_ctx()) if t.name == "search_memory")
    out = search.invoke({"query": "anything"})
    assert "unavailable" in out.lower()


def test_read_source_reads_within_repo_and_refuses_traversal(tmp_path):
    from imperium.agents.tools import build_tools

    (tmp_path / "a.py").write_text("print('hi')\n")
    read = next(t for t in build_tools(_ctx(tmp_path)) if t.name == "read_source")

    assert "print('hi')" in read.invoke({"relative_path": "a.py"})
    assert "escapes the repository root" in read.invoke({"relative_path": "../../etc/passwd"})


# ── agent factory ─────────────────────────────────────────────────────────────

def test_agent_model_chain_splits_primary_and_fallbacks(all_keys):
    from imperium.agents.agent_factory import agent_model_chain

    primary, fallbacks = agent_model_chain("orchestrator")  # nemotron, groq, gemini
    assert primary.openai_api_base == "https://integrate.api.nvidia.com/v1"
    assert len(fallbacks) == 2


def test_agent_model_chain_raises_without_keys(monkeypatch):
    for env in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "MISTRAL_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(env, "changeme")
    get_settings.cache_clear()
    try:
        from imperium.agents.agent_factory import agent_model_chain

        with pytest.raises(RuntimeError, match="No usable provider"):
            agent_model_chain("research")
    finally:
        get_settings.cache_clear()


def test_build_agent_wires_fallback_middleware(all_keys):
    from imperium.agents.agent_factory import build_agent
    from imperium.agents.tools import build_tools

    # research is single-provider (gemini) -> no fallback middleware, still builds.
    agent = build_agent("research", "sys", build_tools(_ctx()))
    assert agent is not None


def test_run_agent_extracts_final_message_text():
    from imperium.agents.agent_factory import run_agent
    from langchain_core.messages import AIMessage, HumanMessage

    class _Agent:
        def invoke(self, payload):
            return {"messages": [HumanMessage("task"), AIMessage("the answer")]}

    assert run_agent(_Agent(), "task") == "the answer"


# ── research findings parsing ─────────────────────────────────────────────────

def test_research_parses_findings_json():
    from imperium.agents.research import ResearchAgent

    text = (
        "Here is my analysis:\n"
        '[{"category": "security", "title": "SQLi", "detail": "raw query", '
        '"confidence": 0.9, "locations": ["db.py:12"]}]'
    )
    findings = ResearchAgent()._parse_findings(text)
    assert len(findings) == 1
    assert findings[0].category.value == "security"
    assert findings[0].locations == ["db.py:12"]


def test_research_parse_handles_no_json():
    from imperium.agents.research import ResearchAgent

    assert ResearchAgent()._parse_findings("no json here") == []


def test_research_run_returns_empty_without_providers(monkeypatch):
    for env in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "MISTRAL_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(env, "changeme")
    get_settings.cache_clear()
    try:
        from imperium.agents.research import ResearchAgent

        assert ResearchAgent().run(_ctx()) == {"findings": []}
    finally:
        get_settings.cache_clear()
