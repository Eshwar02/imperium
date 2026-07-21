"""Orchestrator Agent (TDD §8, PRD §8). Sequences sub-agents end-to-end and enforces
approval-gate checkpoints. This is the spine the API routes call.

Foundation: wiring + method surface with the intended pipeline order documented.
Each step delegates to a sub-agent stub. Fill in per team build order.
"""
from __future__ import annotations

from imperium.agents.base import AgentContext
from imperium.agents.business_logic import BusinessLogicAgent
from imperium.agents.comprehension import ComprehensionAgent
from imperium.agents.compatibility import CompatibilityAgent
from imperium.agents.documentation import DocumentationAgent
from imperium.agents.implementation import ImplementationAgent
from imperium.agents.research import ResearchAgent
from imperium.agents.security import SecurityAgent
from imperium.agents.structure import StructureAgent
from imperium.agents.testing import TestingAgent
from imperium.api.schemas import AnalysisResponse, GateRequest


class Orchestrator:
    """Coordinates the multi-agent pipeline (PRD §7 Steps 1-16)."""

    def __init__(self) -> None:
        self.structure = StructureAgent()
        self.business_logic = BusinessLogicAgent()
        self.security = SecurityAgent()
        self.research = ResearchAgent()
        self.implementation = ImplementationAgent()
        self.compatibility = CompatibilityAgent()
        self.testing = TestingAgent()
        self.documentation = DocumentationAgent()
        self.comprehension = ComprehensionAgent()

    def _context(self, repository_id: str) -> AgentContext:
        # TODO(team): resolve repo_path + rkb handle from RKB by repository_id.
        return AgentContext(repository_id=repository_id, repo_path="")

    # --- Steps 3-6: analysis (parallel sub-agents merged into one report) ---
    def analyze(self, repository_id: str) -> AnalysisResponse:
        """Run structure + business-logic + security + research; merge findings.

        TODO(team): run sub-agents (ideally concurrently), merge into structure_map
        + findings, persist to RKB, generate baseline documentation.
        """
        return AnalysisResponse(repository_id=repository_id, status="queued")

    def get_analysis(self, repository_id: str) -> AnalysisResponse:
        # TODO(team): read persisted analysis from RKB.
        return AnalysisResponse(repository_id=repository_id, status="queued")

    # --- Step 7 & 13: approval gates (category-level, TDD §7 / PRD §9) ---
    def apply_gate_a(self, req: GateRequest) -> dict:
        """Gate A pre-implementation. Only approved categories advance to Step 8.

        TODO(team): persist votes to Decision log; trigger implementation for approved.
        """
        return {"repository_id": req.repository_id, "recorded": len(req.votes), "gate": "A"}

    def apply_gate_b(self, req: GateRequest) -> dict:
        """Gate B pre-merge. Reviews diff + behavioral diff report per category.

        TODO(team): gate on behavioral diff; merge approved categories to integration.
        """
        return {"repository_id": req.repository_id, "recorded": len(req.votes), "gate": "B"}

    # --- Step 7: HITL clarifications (TDD §7) ---
    def pending_clarifications(self, repository_id: str) -> list[dict]:
        # TODO(team): return unverified low-confidence BusinessRule rows as questions.
        return []
