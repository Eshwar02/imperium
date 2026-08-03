"""LLM client — routes each call to the right provider for the calling AGENT ROLE,
with automatic fallback down the chain (see routing.py). NO OpenAI.

Usage:
    from imperium.llm.client import complete
    text = complete("business_logic", prompt, system="...")

The wire format is OpenAI-compatible HTTP only; providers are NVIDIA/Groq/Gemini/
Cerebras/Mistral. This is the one live piece of the spine — real HTTP call, guarded
so a missing key skips to the next provider in the chain instead of crashing.

Features:
  - Provider chain fallback on any error.
  - Exponential backoff with jitter on rate-limit (429) responses.
  - Optional RAG context injection from rkb.embeddings.search.
"""
from __future__ import annotations

import logging
import time

import httpx

from imperium.llm.providers import resolve
from imperium.llm.routing import chain_for

log = logging.getLogger("imperium.llm")

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0   # seconds; doubles per attempt with jitter
_RATE_LIMIT_CODES = {429, 503}


def _call(provider_id: str, prompt: str, system: str | None, temperature: float) -> str:
    provider, api_key, model = resolve(provider_id)
    if not api_key or api_key == "changeme":
        raise RuntimeError(f"No API key for provider '{provider_id}'")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    delay = _RETRY_BASE_DELAY
    for attempt in range(_MAX_RETRIES):
        try:
            resp = httpx.post(
                f"{provider.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": messages, "temperature": temperature},
                timeout=90,
            )
            if resp.status_code in _RATE_LIMIT_CODES and attempt < _MAX_RETRIES - 1:
                import random
                jitter = random.uniform(0, delay * 0.2)
                log.warning(
                    "llm provider=%s HTTP %d — retrying in %.1fs (attempt %d/%d)",
                    provider_id, resp.status_code, delay + jitter, attempt + 1, _MAX_RETRIES,
                )
                time.sleep(delay + jitter)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException as exc:
            if attempt < _MAX_RETRIES - 1:
                log.warning("llm provider=%s timeout — retrying (attempt %d)", provider_id, attempt + 1)
                time.sleep(delay)
                delay *= 2
                continue
            raise

    # Should not reach here
    raise RuntimeError(f"All retries exhausted for provider '{provider_id}'")


def _rag_context(role: str, prompt: str, repository_id: str | None) -> str:
    """Prepend relevant RAG context from Qdrant to the prompt if available."""
    if not repository_id:
        return prompt
    try:
        from imperium.rkb.embeddings import search

        filters = {"repository_id": repository_id}
        results = search(query=prompt[:500], top_k=5, filters=filters)
        if not results:
            return prompt

        context_lines = []
        for r in results:
            payload = r.get("payload", {})
            level = payload.get("level", "")
            text = payload.get("text", "") or payload.get("statement", "") or payload.get("summary", "")
            if text:
                context_lines.append(f"[{level}] {text[:300]}")

        if not context_lines:
            return prompt

        rag_block = "## Relevant Context from Repository Knowledge Base\n" + "\n".join(context_lines)
        return f"{rag_block}\n\n---\n\n{prompt}"
    except Exception as exc:  # noqa: BLE001
        log.debug("RAG context injection failed: %s", exc)
        return prompt


def complete(
    role: str,
    prompt: str,
    system: str | None = None,
    temperature: float = 0.2,
    repository_id: str | None = None,
) -> str:
    """Complete for an agent role, trying its provider chain until one succeeds.

    Args:
        role: Agent role key from routing.py.
        prompt: User prompt text.
        system: Optional system instruction.
        temperature: Sampling temperature (default 0.2 for determinism).
        repository_id: If provided, relevant RKB context is injected via RAG.
    """
    enriched_prompt = _rag_context(role, prompt, repository_id)

    errors: list[str] = []
    for provider_id in chain_for(role):
        try:
            return _call(provider_id, enriched_prompt, system, temperature)
        except Exception as exc:  # noqa: BLE001 — fall through to next provider
            log.warning("llm role=%s provider=%s failed: %s", role, provider_id, exc)
            errors.append(f"{provider_id}: {exc}")
    raise RuntimeError(f"All providers failed for role '{role}': {'; '.join(errors)}")
