"""Scale layer for analysis agents (enterprise codebases).

A single tool-using agent over a whole repository cannot cover — or even fit — a
million-LOC codebase. This module runs analysis as **map-reduce over the module
hierarchy**: each module is analyzed independently with bounded context, modules run
concurrently (capped), and findings are aggregated + deduplicated. Highest-priority
modules (by transformation-priority score) are processed first, so a long run surfaces
the most important findings early and can be capped without losing what matters most.

If the repository has not been indexed into modules yet (small repos, pre-ingestion),
it falls back to a single whole-repo pass.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from imperium.agents.base import AgentContext
from imperium.agents.parsing import parse_findings

log = logging.getLogger("imperium.agents.scale")

# Bounds for a single run. Tune per deployment; a long enterprise run will hit MAX_MODULES.
MAX_MODULES = 300
MAX_WORKERS = 6


def _ordered_modules(repository_id: str) -> list:
    """Fetch modules ordered by transformation priority (highest first)."""
    try:
        from imperium.rkb.store import get_modules, get_priorities, get_session

        session = get_session()
        try:
            modules = get_modules(session, repository_id)
            priorities = get_priorities(session, repository_id)
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001
        log.debug("module fetch failed: %s", exc)
        return []

    # Map any priority reference (path or module id) to a score for ordering.
    score_by_key: dict[str, float] = {}
    for p in priorities:
        key = getattr(p, "path", None) or getattr(p, "module_path", None) or getattr(p, "module_id", None)
        if key is not None:
            score_by_key[str(key)] = float(getattr(p, "score", 0.0) or 0.0)

    def _score(m) -> float:
        return score_by_key.get(str(getattr(m, "path", "")), 0.0)

    return sorted(modules, key=_score, reverse=True)


def run_scaled_findings(
    role: str,
    system_prompt: str,
    ctx: AgentContext,
    task_for_module,
    whole_repo_task: str,
    default_category: str = "modernization",
    default_confidence: float = 0.6,
) -> list[dict]:
    """Map-reduce a findings-producing tool agent over the repository's modules.

    ``task_for_module(module)`` returns the per-module task prompt. Returns a
    deduplicated list of finding dicts, each tagged with its ``module`` when known.
    """
    from imperium.agents.agent_factory import run_tool_agent

    modules = _ordered_modules(ctx.repository_id)[:MAX_MODULES]

    # Fallback: no module index → single whole-repo pass.
    if not modules:
        try:
            text = run_tool_agent(role, system_prompt, whole_repo_task, ctx)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s whole-repo pass failed: %s", role, exc)
            return []
        findings = parse_findings(text, default_category, default_confidence)
        return [f.model_dump() for f in findings]

    def _analyze(module) -> list[dict]:
        # Bound the agent to this module by pointing it at the module's subtree.
        module_ctx = AgentContext(
            repository_id=ctx.repository_id,
            repo_path=ctx.repo_path,
            rkb=ctx.rkb,
            scratch={**ctx.scratch, "module_path": getattr(module, "path", "")},
        )
        try:
            text = run_tool_agent(role, system_prompt, task_for_module(module), module_ctx)
        except Exception as exc:  # noqa: BLE001 — one module failing never fails the run
            log.debug("%s failed on module %s: %s", role, getattr(module, "path", "?"), exc)
            return []
        out = []
        for f in parse_findings(text, default_category, default_confidence):
            d = f.model_dump()
            d["module"] = getattr(module, "path", "")
            out.append(d)
        return out

    aggregated: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(_analyze, m) for m in modules]
        for fut in as_completed(futures):
            aggregated.extend(fut.result())

    return _dedupe(aggregated)


def _dedupe(findings: list[dict]) -> list[dict]:
    """Drop duplicate findings across modules, keyed by (title, first location)."""
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for f in findings:
        locs = f.get("locations") or []
        key = (f.get("title", ""), locs[0] if locs else "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    return unique
