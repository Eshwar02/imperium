"""Business Rule Extractor (TDD §4, §7). The differentiation core (PRD §10).

Surfaces IMPLICIT rules not in comments/docs (undocumented limits, conditional
exceptions). Low-confidence rules become HITL clarification questions; verified
answers persist to RKB (BusinessRule.verified).

TODO(team): combine AST heuristics (guards, clamps, magic constants) + LLM reading
of code slices; return rules with confidence + source locations.
"""
from __future__ import annotations

from imperium.api.schemas import Finding


def extract_rules(repo_path: str, ast_context: object | None = None) -> list[Finding]:
    raise NotImplementedError("business rule extraction — team task (core differentiator)")
