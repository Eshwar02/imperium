"""LLM client — the public API agents call. Routes each call to the right provider
chain for the calling AGENT ROLE (see routing.py) via LangChain, with automatic
fall-through to the next provider on failure. NO OpenAI models.

Usage (unchanged from Phase 0):
    from imperium.llm.client import complete
    text = complete("business_logic", prompt, system="...")

<<<<<<< HEAD
The wire format is OpenAI-compatible HTTP only; providers are NVIDIA/Groq/Gemini/
Cerebras/Mistral. This is the one live piece of the spine — real HTTP call, guarded
so a missing key skips to the next provider in the chain instead of crashing.

Features:
  - Provider chain fallback on any error.
  - Exponential backoff with jitter on rate-limit (429) responses.
  - Optional RAG context injection from rkb.embeddings.search.
=======
New in the LangChain layer:
    from imperium.llm.client import chat, stream, get_token_usage
    msg = chat("research", [("system", "..."), ("user", "...")])
    for chunk in stream("documentation", [("user", "...")]): ...

Providers (NVIDIA/Groq/Cerebras/Mistral) are reached through ``ChatOpenAI``
with a per-provider ``base_url``; construction and fallback wiring live in factory.py.
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
"""
from __future__ import annotations

import logging
<<<<<<< HEAD
import time
=======
import threading
from collections.abc import Iterator, Sequence
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11

from langchain_core.messages import AIMessage, BaseMessage

from imperium.llm.factory import build_runnable

log = logging.getLogger("imperium.llm")

<<<<<<< HEAD
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0   # seconds; doubles per attempt with jitter
_RATE_LIMIT_CODES = {429, 503}

=======
# role -> ("system"|"user"|"assistant", text) pairs, or ready-made BaseMessages.
MessageLike = Sequence[tuple[str, str]] | Sequence[BaseMessage]
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11

# ── Token accounting ──────────────────────────────────────────────────────────
_usage_lock = threading.Lock()
_usage: dict[str, dict[str, int]] = {}


<<<<<<< HEAD
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
=======
def _record_usage(role: str, msg: AIMessage) -> None:
    """Accumulate token usage per role from an AIMessage's ``usage_metadata``."""
    meta = getattr(msg, "usage_metadata", None) or {}
    with _usage_lock:
        bucket = _usage.setdefault(
            role, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0}
        )
        bucket["input_tokens"] += int(meta.get("input_tokens", 0) or 0)
        bucket["output_tokens"] += int(meta.get("output_tokens", 0) or 0)
        bucket["total_tokens"] += int(meta.get("total_tokens", 0) or 0)
        bucket["calls"] += 1


def get_token_usage() -> dict[str, dict[str, int]]:
    """Return a snapshot of accumulated token usage, keyed by agent role."""
    with _usage_lock:
        return {role: dict(counts) for role, counts in _usage.items()}


def reset_token_usage() -> None:
    """Clear accumulated token usage (e.g. at the start of a pipeline run)."""
    with _usage_lock:
        _usage.clear()


# ── Core calls ────────────────────────────────────────────────────────────────

def _to_messages(messages: MessageLike) -> list:
    """Pass BaseMessages through; otherwise treat items as (role, text) tuples."""
    out: list = []
    for m in messages:
        if isinstance(m, BaseMessage):
            out.append(m)
        else:
            role, content = m
            out.append((role, content))
    return out


def chat(role: str, messages: MessageLike, temperature: float = 0.2) -> AIMessage:
    """Invoke ``role``'s provider chain with a message list; return the AIMessage.

    Falls through providers on error (via the runnable's fallbacks). Raises
    ``RuntimeError`` if every provider in the chain fails or none are configured.
    """
    runnable = build_runnable(role, temperature)
    try:
        result = runnable.invoke(_to_messages(messages))
    except Exception as exc:  # noqa: BLE001 — surface a role-scoped error
        raise RuntimeError(f"All providers failed for role '{role}': {exc}") from exc
    if isinstance(result, AIMessage):
        _record_usage(role, result)
    return result


def complete(role: str, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
    """Complete a single prompt for an agent role; return the response text.

    Backwards-compatible with the Phase 0 signature so existing agents are untouched.
    """
    messages: list[tuple[str, str]] = []
    if system:
        messages.append(("system", system))
    messages.append(("user", prompt))
    return chat(role, messages, temperature).text


def stream(role: str, messages: MessageLike, temperature: float = 0.2) -> Iterator[str]:
    """Stream ``role``'s response as text chunks.

    Note: streaming bypasses per-call token accounting (usage arrives only on the
    final chunk and not all gateways report it mid-stream).
    """
    runnable = build_runnable(role, temperature)
    for chunk in runnable.stream(_to_messages(messages)):
        content = getattr(chunk, "content", "")
        if content:
            yield content
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
