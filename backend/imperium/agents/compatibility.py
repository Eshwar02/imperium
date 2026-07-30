"""Compatibility Agent (TDD §8, PRD Step 9). A tool-using agent that validates
existing + proposed integrations against current external API/library versions to
pre-empt near-future breakage, emitting ``Finding(category=integration)``.

Runs on the ``compatibility`` role (Cerebras primary, Groq fallback).
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent

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


def _module_task(module) -> str:
    path = getattr(module, "path", "")
    name = getattr(module, "name", path)
    return (
        f"Review the module '{name}' (path: {path}) for compatibility and deprecation "
        "risk. Use read_source and list_api_endpoints to find external API/library "
        "usage. Return findings JSON."
    )


class CompatibilityAgent(BaseAgent):
    name = "compatibility"
    role = "compatibility"  # → Cerebras primary, Groq fallback

    def run(self, ctx: AgentContext) -> dict:
        """Review integrations/dependencies (map-reduce over modules); return findings."""
        from imperium.agents.scale import run_scaled_findings

        findings = run_scaled_findings(
            self.role,
            _COMPAT_SYSTEM,
            ctx,
            task_for_module=_module_task,
            whole_repo_task=_COMPAT_TASK,
            default_category="integration",
            default_confidence=0.6,
        )
        return {"findings": findings}
