"""Comprehension & Knowledge-Retention Agent (TDD §8, PRD §12.3).

After a change clears Gate B and merges, issues a short (2-3 q) non-blocking check
to the owning engineer targeting that change's decision-log entry. Builds a
per-engineer, per-module comprehension score alongside the module's AI-authorship %.

Two-dimensional drift (PRD §12.1): code drift (stored model vs real behavior) +
comprehension drift (human understanding vs what AI shipped). High-AI-authorship /
low-comprehension modules are flagged back into Gate A.

TODO(team): generate checks from Decision rows; track scores; flag risk modules.
"""
from __future__ import annotations

from imperium.agents.base import AgentContext, BaseAgent


class ComprehensionAgent(BaseAgent):
    name = "comprehension"
    role = "comprehension"  # → Cerebras

    def run(self, ctx: AgentContext) -> dict:
        raise NotImplementedError("comprehension agent — team task")
