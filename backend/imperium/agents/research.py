"""Research Agent (TDD §8, PRD Step 6). A tool-using LangChain agent (Phase 2).

Rather than pre-stuffing context, the agent is given read-only tools over the Repo
Intelligence Engine — semantic memory, the business-rule registry, the timeline, the
call graph, and source — and decides what to retrieve to ground its findings.

Runs on the ``research`` role (Gemini long-context primary, with the routing chain as
fallback middleware).
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent

log = logging.getLogger("imperium.agents.research")

_RESEARCH_SYSTEM = (
    "You are a senior software architect and researcher analyzing a codebase. "
    "You have tools to search semantic memory, list business rules, read the "
    "repository timeline, inspect the call graph (blast radius), and read source. "
    "Investigate using the tools, then identify modernization opportunities, security "
    "risks, and architectural improvements. Ground every finding in evidence you "
    "retrieved. When done, respond with ONLY a JSON array of findings: "
    '[{"category": "modernization|security|performance|integration|documentation", '
    '"title": "...", "detail": "...", "confidence": 0.0, "locations": []}]'
)

_RESEARCH_TASK = (
    "Analyze this repository for modernization opportunities, technical debt, and "
    "risks. Use your tools to gather evidence first, then return the findings JSON."
)


def _module_task(module) -> str:
    path = getattr(module, "path", "")
    name = getattr(module, "name", path)
    return (
        f"Focus your analysis on the module '{name}' (path: {path}). Use read_source on "
        "its files and the graph/memory tools for context. Report modernization "
        "opportunities, technical debt, and risks for this module as findings JSON."
    )


class ResearchAgent(BaseAgent):
    name = "research"
    role = "research"  # → Gemini (long context)

    def run(self, ctx: AgentContext) -> dict:
        """Investigate the repository (map-reduce over modules) and return findings."""
        from imperium.agents.scale import run_scaled_findings

        findings = run_scaled_findings(
            self.role,
            _RESEARCH_SYSTEM,
            ctx,
            task_for_module=_module_task,
            whole_repo_task=_RESEARCH_TASK,
            default_category="modernization",
            default_confidence=0.7,
        )
        return {"findings": findings}
