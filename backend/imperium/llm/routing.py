"""Per-agent model routing (Phase 1). Ordered provider chains = primary → fallback.

Assignment per product spec. Living Audit Agent is Phase II — excluded here.
Chains fall through on error (see client.complete). Test-Generation agent uses two
roles because writing test code (mistral) and reasoning about which edge cases
matter (nemotron) are different jobs.
"""
from __future__ import annotations

# role -> ordered list of provider ids (first = primary, rest = fallback)
ROUTING: dict[str, list[str]] = {
    "orchestrator": ["nemotron", "groq", "gemini"],
    "structure": ["cerebras"],
    "business_logic": ["nemotron", "mistral"],   # mistral = secondary code-nuance check
    "security": ["cerebras"],
    "research": ["gemini"],                        # long-context external synthesis
    "implementation": ["mistral"],                 # Codestral — code generation/migration
    "compatibility": ["cerebras", "groq"],
    "test_codegen": ["mistral"],                   # write test code
    "test_edgecase": ["nemotron"],                 # reason which edge cases matter
    "documentation": ["groq", "gemini"],
    "comprehension": ["cerebras"],
}


def chain_for(role: str) -> list[str]:
    try:
        return ROUTING[role]
    except KeyError as exc:
        raise ValueError(f"No model routing defined for agent role: {role}") from exc
