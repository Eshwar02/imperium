"""Tests for the LangChain-backed LLM factory (Phase 1).

These exercise runnable *construction* only — no network. We assert that per-role
provider chains map onto correctly-configured ChatOpenAI instances, that missing
API keys are skipped, and that fallbacks are wired in chain order.
"""
from __future__ import annotations

import pytest

from imperium.config import get_settings


@pytest.fixture(autouse=True)
def _clear_factory_cache():
    """Model instances are cached per (provider, temperature); reset between tests."""
    from imperium.llm import factory

    factory.clear_cache()
    yield
    factory.clear_cache()


@pytest.fixture
def all_keys(monkeypatch):
    """Give every provider a usable API key and reset the settings cache."""
    for env in (
        "NVIDIA_API_KEY",
        "GROQ_API_KEY",
        "CEREBRAS_API_KEY",
        "MISTRAL_API_KEY",
        "GEMINI_API_KEY",
    ):
        monkeypatch.setenv(env, "sk-test-" + env.lower())
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_models_for_maps_role_to_provider_chain(all_keys):
    from imperium.llm.factory import models_for

    # business_logic -> [nemotron, mistral]
    models = models_for("business_logic")
    assert [m.openai_api_base for m in models] == [
        "https://integrate.api.nvidia.com/v1",
        "https://api.mistral.ai/v1",
    ]
    # Chat Completions, not the Responses API (gateways don't implement it).
    assert all(m.use_responses_api is False for m in models)


def test_single_provider_role_has_no_fallbacks(all_keys):
    from imperium.llm.factory import build_runnable, models_for
    from langchain_openai import ChatOpenAI

    assert len(models_for("structure")) == 1  # cerebras only
    runnable = build_runnable("structure")
    # A single-provider role returns the bare model, not a fallback wrapper.
    assert isinstance(runnable, ChatOpenAI)


def test_multi_provider_role_builds_fallback_chain(all_keys):
    from imperium.llm.factory import build_runnable
    from langchain_core.runnables import RunnableWithFallbacks

    runnable = build_runnable("orchestrator")  # [nemotron, groq, gemini]
    assert isinstance(runnable, RunnableWithFallbacks)
    assert len(runnable.fallbacks) == 2


def test_missing_api_keys_are_skipped(monkeypatch):
    # Only cerebras configured; business_logic (nemotron, mistral) has no keys.
    for env in ("NVIDIA_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(env, "changeme")
    monkeypatch.setenv("CEREBRAS_API_KEY", "sk-real")
    get_settings.cache_clear()
    try:
        from imperium.llm.factory import models_for

        assert models_for("business_logic") == []
        assert len(models_for("structure")) == 1
    finally:
        get_settings.cache_clear()


def test_no_usable_providers_raises(monkeypatch):
    for env in (
        "NVIDIA_API_KEY",
        "GROQ_API_KEY",
        "CEREBRAS_API_KEY",
        "MISTRAL_API_KEY",
        "GEMINI_API_KEY",
    ):
        monkeypatch.setenv(env, "changeme")
    get_settings.cache_clear()
    try:
        from imperium.llm.factory import build_runnable

        with pytest.raises(RuntimeError, match="No usable provider"):
            build_runnable("business_logic")
    finally:
        get_settings.cache_clear()


def test_unknown_role_raises(all_keys):
    from imperium.llm.factory import build_runnable

    with pytest.raises(ValueError, match="No model routing"):
        build_runnable("does_not_exist")
