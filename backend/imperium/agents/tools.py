"""Tools exposed to tool-using LangChain agents (Phase 2).

Each tool wraps a read-only slice of the Repo Intelligence Engine — semantic memory
(Qdrant), the business-rule registry + timeline (Postgres), the call graph (Neo4j),
and repo source. Tools are built *per run* via ``build_tools(ctx)`` so they close over
the current ``repository_id`` / ``repo_path`` and the agent calls them with no extra
plumbing. Every tool is guarded: a missing/unavailable backend returns an explanatory
string rather than raising, so the agent can adapt instead of crashing.
"""
from __future__ import annotations

import logging
import os

from langchain_core.tools import BaseTool, tool

from imperium.agents.base import AgentContext

log = logging.getLogger("imperium.agents.tools")

_MAX_FILE_BYTES = 20_000


def build_tools(ctx: AgentContext) -> list[BaseTool]:
    """Return the read-only tool set bound to this run's repository context."""
    repository_id = ctx.repository_id
    repo_path = ctx.repo_path

    @tool
    def search_memory(query: str) -> str:
        """Semantically search the repository's memory (code, summaries, history).

        Use for "where/what/why" questions about this codebase. Returns the most
        relevant snippets with similarity scores.
        """
        try:
            from imperium.rkb.embeddings import search

            results = search(query=query, top_k=8, filters={"repository_id": repository_id})
        except Exception as exc:  # noqa: BLE001
            log.debug("search_memory unavailable: %s", exc)
            return "Semantic memory is unavailable for this repository."
        if not results:
            return "No relevant memory found for that query."
        return "\n".join(
            f"- [{r.get('score', 0):.2f}] {r.get('payload', {}).get('text', '')[:240]}"
            for r in results
        )

    @tool
    def list_business_rules() -> str:
        """List the business rules extracted from this repository, with confidence."""
        try:
            from imperium.rkb.store import get_business_rules, get_session

            session = get_session()
            try:
                rules = get_business_rules(session, repository_id)
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.debug("list_business_rules unavailable: %s", exc)
            return "The business-rule registry is unavailable."
        if not rules:
            return "No business rules have been extracted yet."
        return "\n".join(f"- [{r.confidence:.0%}] {r.statement}" for r in rules[:40])

    @tool
    def recent_timeline() -> str:
        """Summarize recent repository history (churn, refactors, why code evolved)."""
        try:
            from imperium.rkb.store import get_session, get_timeline

            session = get_session()
            try:
                events = get_timeline(session, repository_id)
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.debug("recent_timeline unavailable: %s", exc)
            return "The repository timeline is unavailable."
        if not events:
            return "No timeline events recorded yet."
        return "\n".join(e.summary for e in events[-20:] if e.summary)

    @tool
    def blast_radius(function_id: str) -> str:
        """List code that depends on a function/module (impact of changing it)."""
        try:
            from imperium.rkb.graph import blast_radius as _blast

            dependents = _blast(function_id=function_id, depth=3)
        except Exception as exc:  # noqa: BLE001
            log.debug("blast_radius unavailable: %s", exc)
            return "The call graph is unavailable."
        if not dependents:
            return f"Nothing depends on '{function_id}' (or it is unknown)."
        return "\n".join(f"- {d.get('id', d)}" for d in dependents[:40])

    @tool
    def list_api_endpoints() -> str:
        """List the API endpoints this repository exposes and consumes (the API graph)."""
        try:
            from imperium.rkb.graph import api_surface

            graph = api_surface(repository_id)
        except Exception as exc:  # noqa: BLE001
            log.debug("list_api_endpoints unavailable: %s", exc)
            return "The API graph is unavailable."
        endpoints = [n for n in graph.get("nodes", []) if n.get("id", "").startswith("api:")]
        if not endpoints:
            return "No API endpoints mapped yet."
        return "\n".join(f"- {n.get('name', n['id'])}" for n in endpoints[:60])

    @tool
    def list_data_access() -> str:
        """List DB tables and where the code reads/writes them (the data graph)."""
        try:
            from imperium.rkb.graph import data_access

            graph = data_access(repository_id)
        except Exception as exc:  # noqa: BLE001
            log.debug("list_data_access unavailable: %s", exc)
            return "The data graph is unavailable."
        edges = graph.get("edges", [])
        if not edges:
            return "No data-access edges mapped yet."
        return "\n".join(
            f"- {e['source'].removeprefix('file:')} {e['type']} {e['target'].removeprefix('table:')}"
            for e in edges[:60]
        )

    @tool
    def read_source(relative_path: str) -> str:
        """Read a source file from the repository by its path relative to the repo root."""
        if not repo_path:
            return "Repository source is not available on disk for this run."
        # Contain reads to the repo root — no traversal outside it.
        full = os.path.normpath(os.path.join(repo_path, relative_path))
        if not full.startswith(os.path.normpath(repo_path)):
            return "Refused: path escapes the repository root."
        if not os.path.isfile(full):
            return f"No such file: {relative_path}"
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                data = fh.read(_MAX_FILE_BYTES + 1)
        except OSError as exc:
            return f"Could not read {relative_path}: {exc}"
        if len(data) > _MAX_FILE_BYTES:
            data = data[:_MAX_FILE_BYTES] + "\n… [truncated]"
        return data

    return [
        search_memory,
        list_business_rules,
        recent_timeline,
        blast_radius,
        list_api_endpoints,
        list_data_access,
        read_source,
    ]
