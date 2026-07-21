"""LLM client — routes each call to the right provider for the calling AGENT ROLE,
with automatic fallback down the chain (see routing.py). NO OpenAI.

Usage:
    from imperium.llm.client import complete
    text = complete("business_logic", prompt, system="...")

The wire format is OpenAI-compatible HTTP only; providers are NVIDIA/Groq/Gemini/
Cerebras/Mistral. This is the one live piece of the spine — real HTTP call, guarded
so a missing key skips to the next provider in the chain instead of crashing.
"""
from __future__ import annotations

import logging

import httpx

from imperium.llm.providers import resolve
from imperium.llm.routing import chain_for

log = logging.getLogger("imperium.llm")


def _call(provider_id: str, prompt: str, system: str | None, temperature: float) -> str:
    provider, api_key, model = resolve(provider_id)
    if not api_key or api_key == "changeme":
        raise RuntimeError(f"No API key for provider '{provider_id}'")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = httpx.post(
        f"{provider.base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": messages, "temperature": temperature},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def complete(role: str, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
    """Complete for an agent role, trying its provider chain until one succeeds.

    TODO(team): streaming, tool-calling, retries/backoff per provider, token
    accounting, RAG context injection from rkb.embeddings.search.
    """
    errors: list[str] = []
    for provider_id in chain_for(role):
        try:
            return _call(provider_id, prompt, system, temperature)
        except Exception as exc:  # noqa: BLE001 — fall through to next provider
            log.warning("llm role=%s provider=%s failed: %s", role, provider_id, exc)
            errors.append(f"{provider_id}: {exc}")
    raise RuntimeError(f"All providers failed for role '{role}': {'; '.join(errors)}")
