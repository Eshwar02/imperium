"""Research Agent (TDD §8, PRD Step 6). A tool-using LangChain agent (Phase 2).

Rather than pre-stuffing context, the agent is given read-only tools over the Repo
Intelligence Engine — semantic memory, the business-rule registry, the timeline, the
call graph, and source — and decides what to retrieve to ground its findings.

Runs on the ``research`` role (Gemini long-context primary, with the routing chain as
fallback middleware).
"""
from __future__ import annotations

import json
import logging
import re

from imperium.agents.base import AgentContext, BaseAgent
from imperium.api.schemas import Category, Finding

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


class ResearchAgent(BaseAgent):
    name = "research"
    role = "research"  # → Gemini (long context)

    def run(self, ctx: AgentContext) -> dict:
        """Investigate the repository with tools and return structured findings."""
        try:
            from imperium.agents.agent_factory import build_agent, run_agent
            from imperium.agents.tools import build_tools

            agent = build_agent(self.role, _RESEARCH_SYSTEM, build_tools(ctx))
            text = run_agent(agent, _RESEARCH_TASK)
        except Exception as exc:  # noqa: BLE001 — no keys / provider down / backend down
            log.warning("Research agent could not run: %s", exc)
            return {"findings": []}

        return {"findings": [f.model_dump() for f in self._parse_findings(text)]}

    def _parse_findings(self, text: str) -> list[Finding]:
        """Extract the JSON findings array from the agent's final message."""
        match = re.search(r"\[.*\]", text or "", re.DOTALL)
        if not match:
            return []
        try:
            raw = json.loads(match.group())
        except json.JSONDecodeError:
            return []
        findings: list[Finding] = []
        for f in raw[:20]:
            try:
                findings.append(
                    Finding(
                        category=Category(f.get("category", "modernization")),
                        title=f.get("title", "Research finding"),
                        detail=f.get("detail", ""),
                        confidence=float(f.get("confidence", 0.7)),
                        locations=f.get("locations", []),
                    )
                )
            except Exception:  # noqa: BLE001 — skip malformed entries
                continue
        return findings
