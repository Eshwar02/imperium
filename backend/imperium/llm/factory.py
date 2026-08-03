"""Build LangChain chat runnables per agent role (Phase 1).

Each role in ``routing.py`` maps to an ordered provider chain (primary → fallback).
We materialise that chain as ``ChatOpenAI`` instances pointed at each provider's
OpenAI-compatible ``base_url`` (see ``providers.py``) and compose them with
``.with_fallbacks()`` so a failing primary transparently rolls to the next provider —
the same fall-through the old httpx ``client.complete`` did, now with retries and a
LangSmith-traceable seam for free.

Providers whose API key is absent/``changeme`` are skipped at build time rather than
left to fail at invoke time. ``ChatOpenAI`` is pinned to the Chat Completions API
(``use_responses_api=False``) because these gateways do not implement the Responses API.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from imperium.llm.providers import resolve
from imperium.llm.routing import chain_for

# Per-provider request tuning. Retries handle transient 429/5xx before we fall through.
_MAX_RETRIES = 2
_TIMEOUT_SECONDS = 90


def _has_key(api_key: str | None) -> bool:
    return bool(api_key) and api_key != "changeme"


@lru_cache(maxsize=128)
def _build_model(provider_id: str, temperature: float) -> ChatOpenAI | None:
    """Construct a ChatOpenAI for one provider, or ``None`` if its key is unset.

    Cached per (provider, temperature): model instances are stateless and reusable.
    """
    provider, api_key, model = resolve(provider_id)
    if not _has_key(api_key):
        return None
    return ChatOpenAI(
        base_url=provider.base_url,
        api_key=api_key,
        model=model,
        temperature=temperature,
        use_responses_api=False,
        max_retries=_MAX_RETRIES,
        timeout=_TIMEOUT_SECONDS,
    )


def models_for(role: str, temperature: float = 0.2) -> list[ChatOpenAI]:
    """Return the usable ChatOpenAI chain for ``role``, in primary→fallback order.

    Providers without a configured API key are omitted. Raises ``ValueError`` for an
    unknown role (propagated from ``chain_for``).
    """
    models = [_build_model(pid, temperature) for pid in chain_for(role)]
    return [m for m in models if m is not None]


def build_runnable(role: str, temperature: float = 0.2) -> Runnable:
    """Build the invokable chat runnable for ``role``.

    Single-provider roles return the bare ``ChatOpenAI``; multi-provider roles return
    the primary wrapped with the rest as ordered fallbacks.
    """
    models = models_for(role, temperature)
    if not models:
        raise RuntimeError(f"No usable provider (missing API keys) for role '{role}'")
    primary, *fallbacks = models
    if not fallbacks:
        return primary
    return primary.with_fallbacks(fallbacks)


def clear_cache() -> None:
    """Drop cached model instances (call after settings/env changes)."""
    _build_model.cache_clear()
