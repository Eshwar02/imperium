"""LLM provider registry (Phase 1). NO OpenAI / OpenRouter — per user constraint.

Providers used in Phase 1: NVIDIA Nemotron, Groq, Gemini, Cerebras, Mistral.
All expose an OpenAI-*compatible* chat-completions wire format (HTTP shape only —
none are OpenAI models), so one client covers them. Each entry: base URL + the env
vars holding its API key and default model.
"""
from __future__ import annotations

from dataclasses import dataclass

from imperium.config import get_settings


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key_attr: str
    model_attr: str


# Registry — keyed by short provider id used in the routing table.
PROVIDERS: dict[str, Provider] = {
    "nemotron": Provider(
        "nemotron", "https://integrate.api.nvidia.com/v1", "nvidia_api_key", "nvidia_model"
    ),
    "groq": Provider(
        "groq", "https://api.groq.com/openai/v1", "groq_api_key", "groq_model"
    ),
    "cerebras": Provider(
        "cerebras", "https://api.cerebras.ai/v1", "cerebras_api_key", "cerebras_model"
    ),
    "mistral": Provider(
        "mistral", "https://api.mistral.ai/v1", "mistral_api_key", "mistral_model"
    ),
    # Gemini exposes an OpenAI-compatible endpoint — keeps the single client working.
    "gemini": Provider(
        "gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "gemini_api_key",
        "gemini_model",
    ),
}


def resolve(provider_id: str) -> tuple[Provider, str, str]:
    """Return (provider, api_key, model) for a provider id, from settings."""
    p = PROVIDERS[provider_id]
    s = get_settings()
    return p, getattr(s, p.api_key_attr), getattr(s, p.model_attr)
