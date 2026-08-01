"""Live agent graph: a run's execution as a node graph (frontend §7b).

Turns a run's event log + current state into a ``{nodes, edges}`` structure the frontend
renders as a live decomposition of the multi-agent run — *how the work is split*, not a
scrolling log. It is derived, not stored: call :func:`build_agent_graph` any time to get
the current snapshot.

Topology (full orchestrator run):

    run ─┬─ build_kb
         ├─ analyze ─┬─ structure
         │           ├─ business_logic
         │           ├─ security
         │           └─ research
         ├─ gate_a   (human gate)
         ├─ simulate
         ├─ gate_b   (human gate)
         └─ finalize

Node status ∈ {idle, active, done, failed, awaiting}. Stage status is derived from the
LangGraph ``{node, delta}`` updates (emitted *after* a stage completes) plus the run's
live status/stage; sub-agent status comes from the fine-grained ``agent_start`` /
``agent_done`` / ``agent_error`` events pushed via :mod:`imperium.core.run_events`.
"""
from __future__ import annotations

from typing import Any

# Pipeline stages, in order. Mirrors graph_orchestrator.build_graph.
STAGES: list[tuple[str, str, str]] = [
    ("build_kb", "Build Knowledge Base", "stage"),
    ("analyze", "Analyze", "stage"),
    ("gate_a", "Gate A · Findings", "gate"),
    ("simulate", "Simulate", "stage"),
    ("gate_b", "Gate B · Behavioral Diff", "gate"),
    ("finalize", "Finalize", "stage"),
]

# Sub-agents that fan out inside `analyze` (mirrors Orchestrator.analyze).
SUBAGENTS: list[tuple[str, str]] = [
    ("structure", "Structure"),
    ("business_logic", "Business Logic"),
    ("security", "Security"),
    ("research", "Research"),
]

_STAGE_IDS = [s[0] for s in STAGES]
_GATE_STAGE = {"gate_a": "A", "gate_b": "B"}


def build_agent_graph(events: list[dict], run: dict) -> dict[str, Any]:
    """Return ``{run_id, status, stage, nodes, edges}`` for the current run state."""
    run_id = run.get("run_id", "")
    run_status = run.get("status", "running")
    current_stage = run.get("stage", "")

    completed = _completed_stages(events)
    agent_status = _agent_statuses(events)
    active_stage = _active_stage(run_status, current_stage, completed)
    pending_gate = (run.get("pending") or {}).get("gate")

    nodes: list[dict] = [
        {
            "id": "run",
            "label": "Orchestrator",
            "type": "run",
            "parent": None,
            "status": _run_node_status(run_status),
            "detail": current_stage,
        }
    ]
    edges: list[dict] = []

    for stage_id, label, kind in STAGES:
        status = _stage_status(
            stage_id, kind, completed, active_stage, run_status, pending_gate
        )
        nodes.append(
            {
                "id": stage_id,
                "label": label,
                "type": kind,
                "parent": "run",
                "status": status,
                "detail": "",
            }
        )
        edges.append({"source": "run", "target": stage_id, "kind": "contains"})

    # Sequence edges between stages (the pipeline flow).
    for a, b in zip(_STAGE_IDS, _STAGE_IDS[1:]):
        edges.append({"source": a, "target": b, "kind": "next"})

    # Sub-agents under `analyze`.
    analyze_active = active_stage == "analyze"
    for agent_id, label in SUBAGENTS:
        status = agent_status.get(agent_id)
        if status is None:
            status = "active" if analyze_active else (
                "done" if "analyze" in completed else "idle"
            )
        nodes.append(
            {
                "id": f"analyze.{agent_id}",
                "label": label,
                "type": "agent",
                "parent": "analyze",
                "status": status,
                "detail": "",
            }
        )
        edges.append(
            {"source": "analyze", "target": f"analyze.{agent_id}", "kind": "contains"}
        )

    return {
        "run_id": run_id,
        "status": run_status,
        "stage": current_stage,
        "nodes": nodes,
        "edges": edges,
    }


# ── derivation helpers ──────────────────────────────────────────────────────────

def _completed_stages(events: list[dict]) -> set[str]:
    """Stages that have emitted their post-completion ``{node, delta}`` update."""
    done = {e["node"] for e in events if e.get("node") in _STAGE_IDS}
    return done


def _agent_statuses(events: list[dict]) -> dict[str, str]:
    """Latest per-sub-agent status from the fine-grained agent_* events."""
    status: dict[str, str] = {}
    for e in events:
        ev, agent = e.get("event"), e.get("agent")
        if not agent:
            continue
        if ev == "agent_start":
            status[agent] = "active"
        elif ev == "agent_done":
            status[agent] = "done"
        elif ev == "agent_error":
            status[agent] = "failed"
    return status


def _active_stage(run_status: str, current_stage: str, completed: set[str]) -> str | None:
    """The stage currently executing, if the run is live."""
    if run_status in ("complete", "failed", "cancelled"):
        return None
    if run_status == "awaiting_gate":
        return current_stage if current_stage in _STAGE_IDS else None
    # running: first stage not yet completed
    for stage_id in _STAGE_IDS:
        if stage_id not in completed:
            return stage_id
    return None


def _run_node_status(run_status: str) -> str:
    return {
        "complete": "done",
        "failed": "failed",
        "cancelled": "failed",
        "awaiting_gate": "awaiting",
    }.get(run_status, "active")


def _stage_status(
    stage_id: str,
    kind: str,
    completed: set[str],
    active_stage: str | None,
    run_status: str,
    pending_gate: str | None,
) -> str:
    if stage_id in completed:
        return "done"
    if stage_id == active_stage:
        # A gate that the run is paused on is "awaiting", not merely active.
        if (
            kind == "gate"
            and run_status == "awaiting_gate"
            and _GATE_STAGE.get(stage_id) == pending_gate
        ):
            return "awaiting"
        return "active"
    if run_status == "failed" and active_stage is None:
        return "idle"
    return "idle"
