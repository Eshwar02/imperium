"""Research Agent (TDD §8, PRD Step 6). Cross-references the repository's
timeline, business rule registry, and semantic memory (Qdrant) to ground
recommendations in current codebase context.

Uses Gemini (long context) as the primary LLM for deep document synthesis.
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent
from imperium.api.schemas import Category, Finding

log = logging.getLogger("imperium.agents.research")

_RESEARCH_SYSTEM = (
    "You are a senior software architect and researcher. "
    "Given information about a codebase's history, business rules, and semantic context, "
    "identify modernization opportunities, security risks, and architectural improvements. "
    "Be specific, cite the evidence provided, and suggest concrete next steps. "
    "Return a JSON array of findings: "
    '[{"category": "modernization|security|performance|integration|documentation", '
    '"title": "...", "detail": "...", "confidence": 0.0, "locations": []}]'
)


class ResearchAgent(BaseAgent):
    name = "research"
    role = "research"  # → Gemini (long context)

    def run(self, ctx: AgentContext) -> dict:
        """Research the repository using timeline + business rules + semantic search."""
        repository_id = ctx.repository_id
        repo_path = ctx.repo_path

        context_parts: list[str] = []
        findings: list[Finding] = []

        # 1. Timeline context
        try:
            from imperium.intelligence.timeline import build_timeline, get_churn_summary

            if repo_path:
                from imperium.rkb.store import get_session, get_timeline

                session = get_session()
                try:
                    events = get_timeline(session, repository_id)
                finally:
                    session.close()

                if not events and repo_path:
                    # First run — build timeline
                    events = build_timeline(repository_id, repo_path, embed=True)

                if events:
                    recent = events[-20:]  # last 20 events
                    timeline_summary = "\n".join(e.summary for e in recent if e.summary)
                    context_parts.append(f"## Repository Timeline (recent events)\n{timeline_summary}")
        except Exception as exc:  # noqa: BLE001
            log.warning("Timeline fetch failed: %s", exc)

        # 2. Business rules context
        try:
            from imperium.rkb.store import get_business_rules, get_session

            session = get_session()
            try:
                rules = get_business_rules(session, repository_id)
            finally:
                session.close()

            if rules:
                rule_summary = "\n".join(
                    f"- [{r.confidence:.0%} confidence] {r.statement}" for r in rules[:30]
                )
                context_parts.append(f"## Extracted Business Rules\n{rule_summary}")
        except Exception as exc:  # noqa: BLE001
            log.warning("Business rules fetch failed: %s", exc)

        # 3. Semantic memory context (Qdrant)
        try:
            from imperium.rkb.embeddings import search

            query = "modernization opportunities and technical debt"
            results = search(
                query=query,
                top_k=10,
                filters={"repository_id": repository_id},
            )
            if results:
                semantic_context = "\n".join(
                    f"- [{r['score']:.2f}] {r['payload'].get('text', '')[:200]}"
                    for r in results
                )
                context_parts.append(f"## Semantic Memory (top relevant)\n{semantic_context}")
        except Exception as exc:  # noqa: BLE001
            log.debug("Semantic search unavailable: %s", exc)

        if not context_parts:
            log.info("No context available for research agent on repo %s", repository_id)
            return {"findings": []}

        full_context = "\n\n".join(context_parts)

        # 4. LLM synthesis
        try:
            from imperium.llm.client import complete
            import json
            import re

            text = complete("research", full_context, system=_RESEARCH_SYSTEM)
            arr_match = re.search(r"\[.*\]", text, re.DOTALL)
            if arr_match:
                raw_findings = json.loads(arr_match.group())
                for f in raw_findings[:20]:
                    try:
                        findings.append(Finding(
                            category=Category(f.get("category", "modernization")),
                            title=f.get("title", "Research finding"),
                            detail=f.get("detail", ""),
                            confidence=float(f.get("confidence", 0.7)),
                            locations=f.get("locations", []),
                        ))
                    except Exception:  # noqa: BLE001
                        continue
        except Exception as exc:  # noqa: BLE001
            log.warning("Research LLM synthesis failed: %s", exc)

        return {"findings": [f.model_dump() for f in findings]}
