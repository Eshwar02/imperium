"""Durable, gated orchestration as a LangGraph StateGraph (Phase 3).

Replaces the fire-and-forget ThreadPoolExecutor spine with a checkpointed state graph
so an enterprise-scale run can take a long time, survive restarts, and **suspend at the
human gates** (LangGraph interrupts) instead of relying on separate API round-trips.

Pipeline:
    build_kb → analyze → [Gate A interrupt] → simulate → [Gate B interrupt] → finalize

The heavy work lives behind a pluggable ``Steps`` object (default delegates to the
existing ``Orchestrator``) so the graph's control flow — fan-out progress, gates,
resumption — is testable without live LLMs or databases.

Checkpointer: Postgres (durable) when reachable, else in-memory. Resume a gate with
``Command(resume=votes)`` on the same ``thread_id`` (the run id).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

log = logging.getLogger("imperium.core.graph_orchestrator")


class RunState(TypedDict, total=False):
    repository_id: str
    repo_path: str
    kb: dict
    structure_map: dict
    findings: list
    gate_a: dict          # {category: approve|reject|defer}
    approved_categories: list
    simulations: list
    gate_b: dict
    docs: dict
    stage: str
    progress: dict


class Steps:
    """Pluggable heavy-work implementations. Default: delegate to ``Orchestrator``."""

    def __init__(self) -> None:
        from imperium.core.orchestrator import Orchestrator

        self._orch = Orchestrator()

    def build_kb(self, state: RunState) -> dict:
        return self._orch.build_knowledge_base(state["repository_id"], state.get("repo_path", ""))

    def analyze(self, state: RunState) -> dict:
        resp = self._orch.analyze(state["repository_id"])
        findings = [f.model_dump() if hasattr(f, "model_dump") else f for f in resp.findings]
        return {"structure_map": resp.structure_map or {}, "findings": findings}

    def simulate(self, state: RunState) -> list:
        # Simulations for approved categories are produced by the intelligence layer;
        # kept minimal here — the real batch pipeline lives in intelligence.simulation.
        return state.get("simulations", [])

    def finalize(self, state: RunState) -> dict:
        docs = self._orch.documentation.run(
            self._orch._context(state["repository_id"])
        )
        self._orch.comprehension.run(self._orch._context(state["repository_id"]))
        return docs.get("docs", {})


def build_graph(steps: Steps | None = None, checkpointer: Any = None):
    """Compile the orchestration StateGraph with gate interrupts and a checkpointer."""
    steps = steps or Steps()
    checkpointer = checkpointer if checkpointer is not None else get_checkpointer()

    def n_build_kb(state: RunState) -> dict:
        kb = steps.build_kb(state)
        return {"kb": kb, "stage": "analyze", "progress": {"kb": "done"}}

    def n_analyze(state: RunState) -> dict:
        out = steps.analyze(state)
        return {
            "structure_map": out.get("structure_map", {}),
            "findings": out.get("findings", []),
            "stage": "gate_a",
            "progress": {**state.get("progress", {}), "analyze": "done"},
        }

    def n_gate_a(state: RunState) -> dict:
        votes = interrupt(
            {
                "gate": "A",
                "reason": "Approve findings per category before transformation.",
                "findings": state.get("findings", []),
            }
        )
        votes = votes or {}
        approved = [c for c, v in votes.items() if v == "approve"]
        return {"gate_a": votes, "approved_categories": approved, "stage": "simulate"}

    def n_simulate(state: RunState) -> dict:
        sims = steps.simulate(state)
        return {
            "simulations": sims,
            "stage": "gate_b",
            "progress": {**state.get("progress", {}), "simulate": "done"},
        }

    def n_gate_b(state: RunState) -> dict:
        votes = interrupt(
            {
                "gate": "B",
                "reason": "Approve the behavioral diff before merge.",
                "simulations": state.get("simulations", []),
            }
        )
        return {"gate_b": votes or {}, "stage": "finalize"}

    def n_finalize(state: RunState) -> dict:
        docs = steps.finalize(state)
        return {
            "docs": docs,
            "stage": "complete",
            "progress": {**state.get("progress", {}), "finalize": "done"},
        }

    g = StateGraph(RunState)
    g.add_node("build_kb", n_build_kb)
    g.add_node("analyze", n_analyze)
    g.add_node("gate_a", n_gate_a)
    g.add_node("simulate", n_simulate)
    g.add_node("gate_b", n_gate_b)
    g.add_node("finalize", n_finalize)

    g.add_edge(START, "build_kb")
    g.add_edge("build_kb", "analyze")
    g.add_edge("analyze", "gate_a")
    g.add_edge("gate_a", "simulate")
    g.add_edge("simulate", "gate_b")
    g.add_edge("gate_b", "finalize")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer)


def get_checkpointer() -> Any:
    """Return a durable Postgres checkpointer if reachable, else an in-memory one."""
    try:
        from imperium.config import get_settings

        dsn = get_settings().postgres_dsn
        # LangGraph's PostgresSaver expects a libpq DSN (no SQLAlchemy driver prefix).
        dsn = dsn.replace("postgresql+psycopg://", "postgresql://")
        from langgraph.checkpoint.postgres import PostgresSaver

        saver_cm = PostgresSaver.from_conn_string(dsn)
        saver = saver_cm.__enter__()
        saver.setup()
        log.info("Using Postgres checkpointer for durable runs")
        return saver
    except Exception as exc:  # noqa: BLE001 — dev / DB down
        log.warning("Postgres checkpointer unavailable (%s); using in-memory", exc)
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()
