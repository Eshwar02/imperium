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


def run_agent(agent, user_message: str) -> str:
    """Invoke a built agent with a single user turn; return the final assistant text."""
    result = agent.invoke({"messages": [("user", user_message)]})
    messages = result.get("messages", [])
    if not messages:
        return ""
    last = messages[-1]
    text = getattr(last, "text", None)
    if isinstance(text, str):  # `.text` property (current API)
        return text
    if callable(text):  # legacy `.text()` method
        return text()
    content = getattr(last, "content", "")
    return content if isinstance(content, str) else str(content)
