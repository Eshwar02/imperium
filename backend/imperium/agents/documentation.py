"""Documentation Agent (TDD §8, PRD §11). Synthesizes analysis + decisions + test
results into the full documentation suite (docs as exhaust, not a chore).

Outputs (TDD §8): architecture, module, business-rule catalog, DB, API, integration,
dependency reports, Mermaid flowcharts, sequence diagrams, call graphs. Plus changelog
+ decision log + data-flow/privacy doc (PRD §11).

TODO(team): render Markdown (exportable to PDF/Confluence/Word), Mermaid diagram-as-code.
"""
from __future__ import annotations

from imperium.agents.base import AgentContext, BaseAgent


class DocumentationAgent(BaseAgent):
    name = "documentation"
    role = "documentation"  # → Groq primary, Gemini fallback

    def run(self, ctx: AgentContext) -> dict:
        raise NotImplementedError("documentation agent — team task")
