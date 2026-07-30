"""Documentation Agent (TDD §8, PRD §11). Synthesizes analysis + decisions + test
results into the full documentation suite (docs as exhaust, not a chore).

Outputs:
  - Architecture overview (Markdown + Mermaid graph)
  - Module-level docs
  - Business-rule catalog
  - Decision log summary
  - API + DB reference
  - Dependency report
  - Mermaid flowcharts / sequence diagrams
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent

log = logging.getLogger("imperium.agents.documentation")

_DOC_SYSTEM = (
    "You are a senior technical writer and architect. "
    "Generate clear, accurate, and complete Markdown documentation. "
    "Use Mermaid diagram syntax for diagrams (fenced with ```mermaid). "
    "Be concise but comprehensive. Focus on the WHY, not just the WHAT."
)


class DocumentationAgent(BaseAgent):
    name = "documentation"
    role = "documentation"  # → Groq primary, Gemini fallback

    def run(self, ctx: AgentContext) -> dict:
        """Generate the full documentation suite for a repository."""
        repository_id = ctx.repository_id
        repo_path = ctx.repo_path

        docs: dict[str, str] = {}

        # Gather inputs
        modules = self._fetch_modules(repository_id)
        rules = self._fetch_rules(repository_id)
        decisions = self._fetch_decisions(repository_id)
        doc_data = self._extract_existing_docs(repo_path)
        graph_data = self._fetch_graph(repository_id)

        # Generate documentation sections
        docs["architecture"] = self._gen_architecture(modules, graph_data, repository_id)
        docs["business_rules"] = self._gen_rules_catalog(rules, repository_id)
        docs["decision_log"] = self._gen_decision_log(decisions, repository_id)
        docs["modules"] = self._gen_module_docs(modules, doc_data, repository_id)

        return {"docs": docs, "repository_id": repository_id}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch_modules(self, repository_id: str) -> list:
        try:
            from imperium.rkb.store import get_modules, get_session

            session = get_session()
            try:
                return get_modules(session, repository_id)
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("fetch modules failed: %s", exc)
            return []

    def _fetch_rules(self, repository_id: str) -> list:
        try:
            from imperium.rkb.store import get_business_rules, get_session

            session = get_session()
            try:
                return get_business_rules(session, repository_id)
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("fetch rules failed: %s", exc)
            return []

    def _fetch_decisions(self, repository_id: str) -> list:
        try:
            from imperium.rkb.store import get_decisions, get_session

            session = get_session()
            try:
                return get_decisions(session, repository_id)
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("fetch decisions failed: %s", exc)
            return []

    def _extract_existing_docs(self, repo_path: str) -> dict:
        if not repo_path:
            return {}
        try:
            from imperium.intelligence.doc_extractor import extract

            return extract(repo_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("doc extraction failed: %s", exc)
            return {}

    def _fetch_graph(self, repository_id: str) -> dict:
        try:
            from imperium.rkb.graph import repo_graph

            return repo_graph(repository_id)
        except Exception as exc:  # noqa: BLE001
            log.debug("graph fetch failed: %s", exc)
            return {"nodes": [], "edges": []}

    # ── Section generators ────────────────────────────────────────────────────

    def _gen_architecture(self, modules: list, graph: dict, repository_id: str) -> str:
        module_list = "\n".join(f"- **{m.name}** (`{m.path}`) — {m.summary or 'no summary'}" for m in modules[:30])
        nodes = graph.get("nodes", [])[:20]
        edges = graph.get("edges", [])[:30]

        mermaid_nodes = "\n  ".join(f'{n["id"]}["{n.get("name", n["id"])}"]' for n in nodes)
        mermaid_edges = "\n  ".join(f'{e["source"]} --> {e["target"]}' for e in edges)
        mermaid = f"```mermaid\ngraph TD\n  {mermaid_nodes}\n  {mermaid_edges}\n```" if nodes else ""

        prompt = (
            f"Repository: {repository_id}\n\n"
            f"Modules:\n{module_list}\n\n"
            f"Call Graph (Mermaid):\n{mermaid}\n\n"
            "Write an architecture overview in Markdown including: purpose, modules, "
            "key dependencies, and the Mermaid diagram above."
        )
        return self._llm(prompt) or f"# Architecture\n\n{module_list}\n\n{mermaid}"

    def _gen_rules_catalog(self, rules: list, repository_id: str) -> str:
        if not rules:
            return "# Business Rules\n\nNo rules extracted yet."
        lines = []
        for i, r in enumerate(rules, 1):
            conf = f"{r.confidence:.0%}"
            status = "✅ Verified" if r.verified else f"⚠️ {conf} confidence"
            lines.append(f"### Rule {i}: {r.statement[:120]}\n- Status: {status}\n- Locations: {r.locations}")
        return "# Business Rules Catalog\n\n" + "\n\n".join(lines)

    def _gen_decision_log(self, decisions: list, repository_id: str) -> str:
        if not decisions:
            return "# Decision Log\n\nNo decisions recorded yet."
        lines = ["# Decision Log\n\n| # | Category | Change | Gate | Verdict | Date |", "|---|----------|--------|------|---------|------|"]
        for i, d in enumerate(decisions[-50:], 1):
            date = d.created_at.strftime("%Y-%m-%d") if d.created_at else "-"
            lines.append(f"| {i} | {d.category} | {d.change_summary[:60]} | {d.gate or '-'} | {d.verdict or '-'} | {date} |")
        return "\n".join(lines)

    def _gen_module_docs(self, modules: list, doc_data: dict, repository_id: str) -> str:
        if not modules:
            return "# Module Reference\n\nNo modules indexed yet."

        module_summaries = doc_data.get("module_summaries", {})
        sections = ["# Module Reference\n"]

        for m in modules[:20]:
            summary = m.summary or module_summaries.get(m.path, "") or "No summary available."
            ai_pct = f"{m.ai_authorship_pct:.0f}%"
            flag = " 🚩 (flagged for review)" if m.flagged_for_review else ""
            sections.append(
                f"## `{m.name}`\n**Path:** `{m.path}`  \n**AI Authorship:** {ai_pct}{flag}\n\n{summary}\n"
            )

        return "\n".join(sections)

    def _llm(self, prompt: str) -> str | None:
        try:
            from imperium.llm.client import complete

            return complete("documentation", prompt, system=_DOC_SYSTEM, temperature=0.2)
        except Exception as exc:  # noqa: BLE001
            log.warning("Documentation LLM call failed: %s", exc)
            return None
