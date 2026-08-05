"""Quick, dependency-light way to test the agent workflow on a local folder.

Usage:
    cd backend
    .venv/bin/python scripts/try_agents.py <path-to-code>

What it does (each part degrades gracefully):
  1. Multi-graph  — parses the folder and prints call/API/data/dependency graph counts
                    (NO API keys, NO databases needed).
  2. Security scan — deterministic vulnerability findings (NO keys needed).
  3. Research agent — a live LLM tool-using agent, ONLY if an LLM key is configured
                    (falls back to a message if not).
"""
from __future__ import annotations

import sys

from imperium.agents.base import AgentContext


def main(path: str) -> None:
    ctx = AgentContext(repository_id="local-test", repo_path=path)

    print(f"\n=== Imperium agent workflow test on: {path} ===\n")

    # 1. Multi-graph (offline) ---------------------------------------------------
    from imperium.intelligence.multigraph import build_multigraph

    mg = build_multigraph("local-test", path, write=False)
    kinds: dict[str, int] = {}
    for n in mg["nodes"]:
        kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
    print("[1] Multi-graph (offline, no keys):")
    print(f"    counts: {mg['counts']}")
    print(f"    node kinds: {kinds}")
    endpoints = [n["name"] for n in mg["nodes"] if n["kind"] == "Endpoint"][:5]
    tables = [n["name"] for n in mg["nodes"] if n["kind"] == "Table"][:5]
    if endpoints:
        print(f"    sample endpoints: {endpoints}")
    if tables:
        print(f"    sample tables: {tables}")

    # 2. Deterministic security scan (offline) -----------------------------------
    from imperium.intelligence.security_scanner import scan

    sec = scan(path)
    print(f"\n[2] Security scan (offline, no keys): {len(sec)} findings")
    for f in sec[:5]:
        print(f"    - [{f.confidence:.0%}] {f.title} @ {f.locations}")

    # 3. Live research agent (needs an LLM key) ----------------------------------
    from imperium.llm.routing import chain_for
    from imperium.llm.providers import resolve

    has_key = any(resolve(p)[1] not in ("", "changeme") for p in chain_for("research"))
    print("\n[3] Research agent (needs LLM key):")
    if not has_key:
        print("    SKIPPED — no LLM key set for the 'research' role. Add one to .env to enable.")
        return
    from imperium.agents.research import ResearchAgent

    result = ResearchAgent().run(ctx)
    findings = result.get("findings", [])
    print(f"    {len(findings)} findings")
    for f in findings[:5]:
        print(f"    - [{f.get('category')}] {f.get('title')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python scripts/try_agents.py <path-to-code>")
        sys.exit(1)
    main(sys.argv[1])
