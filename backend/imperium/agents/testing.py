"""Test-Generation & Verification Agents (TDD §8, PRD §10). Generate + run
security/data-flow/load/usability/performance/edge-case tests; produce the
behavioral diff report — Imperium's core evidence artifact.

Runs TWICE: baseline (pre-change) then post-change, then diffs (PRD Step 10-12).
Edge cases derive from extracted business rules, not generic boilerplate.

TODO(team): generate tests, execute via sandbox.runner against baseline + changed
code, store TestResult rows, build behavioral diff.
"""
from __future__ import annotations

from imperium.agents.base import AgentContext, BaseAgent


class TestingAgent(BaseAgent):
    name = "testing"
    # Two roles: write test code vs reason about edge cases (llm/routing.py)
    role_codegen = "test_codegen"    # → Mistral Codestral
    role_edgecase = "test_edgecase"  # → Nemotron

    def run(self, ctx: AgentContext) -> dict:
        raise NotImplementedError("testing/verification agent — team task")

    def behavioral_diff(self, ctx: AgentContext) -> dict:
        """Compare baseline vs post-change results into an itemized risk report."""
        raise NotImplementedError("behavioral diff — team task")
