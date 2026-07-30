"""Build tool-using LangChain agents per role (Phase 2).

Wraps ``langchain.agents.create_agent`` so every deep agent runs its role's provider
chain: the primary model drives the reason→act loop, and the remaining providers from
``routing.py`` become ``ModelFallbackMiddleware`` — the agent-loop equivalent of the
Phase 1 ``.with_fallbacks()`` used for one-shot calls.

Agents built here keep the ``BaseAgent.run(ctx)`` contract: callers invoke via
``run_agent`` and get back the final assistant text to parse.
"""
from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from imperium.llm.factory import models_for


def agent_model_chain(role: str, temperature: float = 0.2) -> tuple[ChatOpenAI, list[ChatOpenAI]]:
    """Return (primary_model, fallback_models) for a role's provider chain.

    Raises ``RuntimeError`` when no provider for the role has a configured key.
    """
    models = models_for(role, temperature)
    if not models:
        raise RuntimeError(f"No usable provider (missing API keys) for role '{role}'")
    primary, *fallbacks = models
    return primary, fallbacks


def build_agent(
    role: str,
    system_prompt: str,
    tools: list[BaseTool],
    temperature: float = 0.2,
):
    """Create a tool-using agent for ``role`` with fallback middleware over its chain."""
    primary, fallbacks = agent_model_chain(role, temperature)
    middleware = [ModelFallbackMiddleware(*fallbacks)] if fallbacks else []
    return create_agent(
        model=primary,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
    )


def _message_text(msg) -> str:
    """Best-effort plain-text of a LangChain message across API versions."""
    text = getattr(msg, "text", None)
    if isinstance(text, str):  # `.text` property (current API)
        return text
    if callable(text):  # legacy `.text()` method
        return text()
    content = getattr(msg, "content", "")
    return content if isinstance(content, str) else str(content)


def run_agent(agent, user_message: str) -> str:
    """Invoke a built agent with a single user turn; return the final assistant text."""
    result = agent.invoke({"messages": [("user", user_message)]})
    messages = result.get("messages", [])
    if not messages:
        return ""
    return _message_text(messages[-1])


def _message_events(msg) -> list[dict]:
    """Translate one streamed message into live events (tool calls / results / text)."""
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:  # AI message that decided to call tools
        return [
            {"type": "tool_call", "name": tc.get("name", ""), "args": tc.get("args", {})}
            for tc in tool_calls
        ]
    if msg.__class__.__name__ == "ToolMessage":  # a tool returned
        return [{
            "type": "tool_result",
            "name": getattr(msg, "name", ""),
            "content": _message_text(msg)[:2000],
        }]
    text = _message_text(msg)
    return [{"type": "message", "text": text}] if text.strip() else []


def run_agent_stream(agent, user_message: str):
    """Stream a single agent turn, yielding events as tool calls and messages occur.

    Events (dicts):
      {"type": "tool_call",   "name", "args"}   — the model decided to call a tool
      {"type": "tool_result", "name", "content"}— a tool returned
      {"type": "message",     "text"}           — assistant text
      {"type": "final",       "text"}           — the last assistant text (terminal)
    """
    final_text = ""
    for chunk in agent.stream({"messages": [("user", user_message)]}, stream_mode="updates"):
        for update in (chunk.values() if isinstance(chunk, dict) else []):
            messages = update.get("messages", []) if isinstance(update, dict) else []
            for msg in messages:
                for ev in _message_events(msg):
                    if ev["type"] == "message":
                        final_text = ev["text"]
                    yield ev
    yield {"type": "final", "text": final_text}


def run_tool_agent(
    role: str,
    system_prompt: str,
    task: str,
    ctx,
    temperature: float = 0.2,
) -> str:
    """Build a tool-using agent for ``role`` bound to ``ctx`` and run one task turn.

    Convenience for the analysis agents that all follow build-tools → build-agent →
    run pattern. Imports ``build_tools`` lazily to avoid a module import cycle.
    """
    from imperium.agents.tools import build_tools

    agent = build_agent(role, system_prompt, build_tools(ctx), temperature)
    return run_agent(agent, task)
