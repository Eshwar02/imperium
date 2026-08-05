"""Run manager: drives durable orchestration runs and exposes their state.

Wraps the compiled LangGraph so the API layer can start a run, inspect its progress,
stream its events, and resume it past a human gate — all keyed by a ``run_id`` that is
also the checkpointer ``thread_id`` (so state is durable and resumable).

Runs advance to the next **interrupt** (a gate) or to completion. The API layer decides
whether to drive them in a background task; driving itself is synchronous and
deterministic so it can be tested without threads.
"""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Any

from langgraph.types import Command

log = logging.getLogger("imperium.core.runs")


class RunManager:
    def __init__(self, graph: Any = None) -> None:
        self._graph = graph
        self._lock = threading.Lock()
        # run_id -> {status, stage, progress, pending, events}
        self._runs: dict[str, dict] = {}

    @property
    def graph(self):
        if self._graph is None:
            from imperium.core.graph_orchestrator import build_graph

            self._graph = build_graph()
        return self._graph

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def register(self, owner_id: str | None = None, repository_id: str | None = None) -> str:
        """Create a run entry (status=running) and return its id — does not drive it.

        owner_id: Supabase user id that owns this run, so the API can scope
        list/get/delete/resume to the caller. None = unclaimed (dev/system).
        """
        run_id = uuid.uuid4().hex
        with self._lock:
            self._runs[run_id] = {
                "status": "running",
                "stage": "build_kb",
                "progress": {},
                "pending": None,
                "owner_id": owner_id,
                "repository_id": repository_id,
                "events": [],
            }
        return run_id

    def begin(self, run_id: str, repository_id: str, repo_path: str = "") -> None:
        """Drive a registered run from the start to its first gate/completion."""
        self._drive(run_id, {"repository_id": repository_id, "repo_path": repo_path})

    def start_run(
        self, repository_id: str, repo_path: str = "", owner_id: str | None = None
    ) -> str:
        """Register and drive a run synchronously (convenience; API uses register+begin)."""
        run_id = self.register(owner_id=owner_id, repository_id=repository_id)
        self.begin(run_id, repository_id, repo_path)
        return run_id

    def owner_of(self, run_id: str) -> str | None:
        """Return the owner id of a run (None if unclaimed). Raises KeyError if unknown."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(run_id)
            return run.get("owner_id")

    def resume_gate(self, run_id: str, votes: dict) -> dict:
        """Resume a run paused at a gate with the human's votes; drive to the next stop."""
        if run_id not in self._runs:
            raise KeyError(run_id)
        self._drive(run_id, Command(resume=votes))
        return self.get_run(run_id)

    # ── introspection ─────────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> dict:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(run_id)
            return {k: v for k, v in run.items() if k != "events"} | {"run_id": run_id}

    def get_events(self, run_id: str) -> list[dict]:
        with self._lock:
            run = self._runs.get(run_id)
            return list(run["events"]) if run else []

    def list_runs(self, owner_id: str | None = None) -> list[dict]:
        """Summaries of every known run (no event log).

        owner_id: when given, return only runs owned by that user (plus unclaimed
        runs whose owner_id is None). When None, return all — callers that need
        isolation must pass the authenticated user id.
        """
        with self._lock:
            return [
                {k: v for k, v in run.items() if k != "events"} | {"run_id": rid}
                for rid, run in self._runs.items()
                if owner_id is None or run.get("owner_id") in (None, owner_id)
            ]

    def delete(self, run_id: str) -> None:
        """Forget a run entirely (its live node graph becomes deletable)."""
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(run_id)
            del self._runs[run_id]

    def agent_graph(self, run_id: str) -> dict:
        """The run's live execution as a ``{nodes, edges}`` agent graph."""
        from imperium.core.agent_graph import build_agent_graph

        run = self.get_run(run_id)  # raises KeyError if unknown
        return build_agent_graph(self.get_events(run_id), run)

    # ── internal ──────────────────────────────────────────────────────────────

    def _drive(self, run_id: str, graph_input: Any) -> None:
        from imperium.core.run_events import reset_emitter, set_emitter

        config = {"configurable": {"thread_id": run_id}}
        # Bind this run's event sink so deep sub-agents can push live progress.
        token = set_emitter(lambda ev: self._emit(run_id, ev))
        try:
            for update in self.graph.stream(graph_input, config, stream_mode="updates"):
                for node, delta in (update or {}).items():
                    self._emit(run_id, {"node": node, "delta": _summarize(delta)})
        except Exception as exc:  # noqa: BLE001
            self._set(run_id, status="failed", pending={"error": str(exc)[:300]})
            log.warning("Run %s failed: %s", run_id, exc)
            return
        finally:
            reset_emitter(token)
        self._sync_state(run_id, config)

    def _sync_state(self, run_id: str, config: dict) -> None:
        snap = self.graph.get_state(config)
        values = snap.values or {}
        stage = values.get("stage", "unknown")
        progress = values.get("progress", {})
        if snap.next:  # paused at an interrupt (a gate)
            pending = None
            for task in snap.tasks:
                if getattr(task, "interrupts", None):
                    pending = task.interrupts[0].value
            self._set(run_id, status="awaiting_gate", stage=stage, progress=progress, pending=pending)
            self._emit(run_id, {"event": "awaiting_gate", "gate": (pending or {}).get("gate")})
        else:
            self._set(run_id, status="complete", stage=stage, progress=progress, pending=None)
            self._emit(run_id, {"event": "complete"})

    def _set(self, run_id: str, **fields) -> None:
        with self._lock:
            self._runs[run_id].update(fields)

    def _emit(self, run_id: str, event: dict) -> None:
        with self._lock:
            self._runs[run_id]["events"].append(event)


def _summarize(delta: Any) -> dict:
    """Compact a node's state delta for the event log (avoid dumping big payloads)."""
    if not isinstance(delta, dict):
        return {}
    out: dict[str, Any] = {}
    for k, v in delta.items():
        if isinstance(v, list):
            out[k] = f"[{len(v)} items]"
        elif isinstance(v, dict):
            out[k] = {kk: ("…" if isinstance(vv, (list, dict)) else vv) for kk, vv in v.items()}
        else:
            out[k] = v
    return out


# Process-wide singleton used by the API layer.
run_manager = RunManager()
