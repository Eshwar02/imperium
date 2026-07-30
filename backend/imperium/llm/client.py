"""LLM client — the public API agents call. Routes each call to the right provider
chain for the calling AGENT ROLE (see routing.py) via LangChain, with automatic
fall-through to the next provider on failure. NO OpenAI models.

Usage (unchanged from Phase 0):
    from imperium.llm.client import complete
    text = complete("business_logic", prompt, system="...")

New in the LangChain layer:
    from imperium.llm.client import chat, stream, get_token_usage
    msg = chat("research", [("system", "..."), ("user", "...")])
    for chunk in stream("documentation", [("user", "...")]): ...

Providers (NVIDIA/Groq/Gemini/Cerebras/Mistral) are reached through ``ChatOpenAI``
with a per-provider ``base_url``; construction and fallback wiring live in factory.py.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Iterator, Sequence

from langchain_core.messages import AIMessage, BaseMessage

from imperium.llm.factory import build_runnable

log = logging.getLogger("imperium.llm")

# role -> ("system"|"user"|"assistant", text) pairs, or ready-made BaseMessages.
MessageLike = Sequence[tuple[str, str]] | Sequence[BaseMessage]

# ── Token accounting ──────────────────────────────────────────────────────────
_usage_lock = threading.Lock()
_usage: dict[str, dict[str, int]] = {}


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
