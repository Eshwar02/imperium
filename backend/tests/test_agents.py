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
    for env in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "MISTRAL_API_KEY"):
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
    assert names == {
        "search_memory",
        "list_business_rules",
        "recent_timeline",
        "blast_radius",
        "list_api_endpoints",
        "list_data_access",
        "read_source",
    }


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

    primary, fallbacks = agent_model_chain("orchestrator")  # nemotron, groq
    assert primary.openai_api_base == "https://integrate.api.nvidia.com/v1"
    assert len(fallbacks) == 1


def test_agent_model_chain_raises_without_keys(monkeypatch):
    for env in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "MISTRAL_API_KEY"):
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

    # research is multi-provider (nemotron -> groq) -> fallback middleware, builds fine.
    agent = build_agent("research", "sys", build_tools(_ctx()))
    assert agent is not None


def test_run_agent_extracts_final_message_text():
    from imperium.agents.agent_factory import run_agent
    from langchain_core.messages import AIMessage, HumanMessage

    class _Agent:
        def invoke(self, payload):
            return {"messages": [HumanMessage("task"), AIMessage("the answer")]}

    assert run_agent(_Agent(), "task") == "the answer"


# ── findings parsing (shared) ─────────────────────────────────────────────────

def test_parse_findings_extracts_json():
    from imperium.agents.parsing import parse_findings

    text = (
        "Here is my analysis:\n"
        '[{"category": "security", "title": "SQLi", "detail": "raw query", '
        '"confidence": 0.9, "locations": ["db.py:12"]}]'
    )
    findings = parse_findings(text)
    assert len(findings) == 1
    assert findings[0].category.value == "security"
    assert findings[0].locations == ["db.py:12"]


def test_parse_findings_applies_default_category():
    from imperium.agents.parsing import parse_findings

    findings = parse_findings('[{"title": "x", "detail": "y"}]', default_category="integration")
    assert findings[0].category.value == "integration"


def test_parse_findings_handles_no_json_and_malformed():
    from imperium.agents.parsing import parse_findings

    assert parse_findings("no json here") == []
    # malformed entries are skipped individually
    assert parse_findings('[{"category": "nope"}, {"title": "ok", "detail": "d"}]') != []


# ── analysis agents degrade gracefully without providers ──────────────────────

def test_analysis_agents_return_empty_without_providers(monkeypatch):
    for env in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.setenv(env, "changeme")
    get_settings.cache_clear()
    try:
        from imperium.agents.research import ResearchAgent
        from imperium.agents.security import SecurityAgent
        from imperium.agents.compatibility import CompatibilityAgent

        assert ResearchAgent().run(_ctx()) == {"findings": []}
        assert SecurityAgent().run(_ctx()) == {"findings": []}
        assert CompatibilityAgent().run(_ctx()) == {"findings": []}
    finally:
        get_settings.cache_clear()


def test_business_logic_without_repo_path_returns_empty():
    from imperium.agents.business_logic import BusinessLogicAgent

    assert BusinessLogicAgent().run(_ctx()) == {"findings": []}


def test_implementation_without_repo_path_returns_empty():
    from imperium.agents.implementation import ImplementationAgent

    assert ImplementationAgent().run(_ctx()) == {"proposed_changes": []}


def test_structure_returns_structure_map(monkeypatch):
    from imperium.agents import structure

    monkeypatch.setattr("imperium.rkb.graph.repo_graph", lambda rid: {"nodes": [{"id": "a"}], "edges": []})
    out = structure.StructureAgent().run(_ctx())
    assert out["structure_map"]["nodes"] == [{"id": "a"}]
    assert out["findings"] == []


def test_testing_behavioral_diff_flags_regression(monkeypatch):
    from imperium.agents.testing import TestingAgent

    class _Row:
        def __init__(self, phase, dimension, payload):
            self.phase, self.dimension, self.payload = phase, dimension, payload

    rows = [
        _Row("baseline", "behavior", {"passed": True}),
        _Row("post_change", "behavior", {"passed": False}),
        _Row("baseline", "security", {"passed": True}),
        _Row("post_change", "security", {"passed": True}),
    ]

    class _Q:
        def filter_by(self, **k):
            return self

        def all(self):
            return rows

    class _Session:
        def query(self, *a):
            return _Q()

        def close(self):
            pass

    monkeypatch.setattr("imperium.rkb.store.get_session", lambda: _Session())
    diff = TestingAgent().behavioral_diff(_ctx())
    assert diff["regressions"] == 1
    assert diff["safe"] is False
    behavior = next(r for r in diff["report"] if r["dimension"] == "behavior")
    assert behavior["regression"] is True
