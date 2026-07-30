"""Compatibility Agent (TDD §8, PRD Step 9). A tool-using agent that validates
existing + proposed integrations against current external API/library versions to
pre-empt near-future breakage, emitting ``Finding(category=integration)``.

Runs on the ``compatibility`` role (Cerebras primary, Groq fallback).
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent
from imperium.agents.parsing import parse_findings

log = logging.getLogger("imperium.agents.compatibility")

_COMPAT_SYSTEM = (
    "You are an integration/compatibility reviewer. Use your tools to read dependency "
    "manifests and source, and search semantic memory for external API usage. Identify "
    "deprecated APIs, pinned-but-outdated dependencies, breaking-change risk, and "
    "version mismatches between components. Report only concrete issues with evidence. "
    "Respond with ONLY a JSON array: "
    '[{"category": "integration", "title": "...", "detail": "...", '
    '"confidence": 0.0, "locations": ["file:line"]}]'
)

_COMPAT_TASK = (
    "Review this repository's integrations and dependencies for compatibility and "
    "deprecation risk. Gather evidence with your tools first, then return the JSON."
)


class CompatibilityAgent(BaseAgent):
    name = "compatibility"
    role = "compatibility"  # → Cerebras primary, Groq fallback

    def run(self, ctx: AgentContext) -> dict:
        """Review integrations/dependencies and return compatibility findings."""
        try:
            from imperium.agents.agent_factory import run_tool_agent

            text = run_tool_agent(self.role, _COMPAT_SYSTEM, _COMPAT_TASK, ctx)
        except Exception as exc:  # noqa: BLE001
            log.warning("Compatibility agent could not run: %s", exc)
            return {"findings": []}

        findings = parse_findings(text, default_category="integration", default_confidence=0.6)
        return {"findings": [f.model_dump() for f in findings]}
