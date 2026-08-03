"""Run-scoped event emitter for live agent progress.

The durable LangGraph run streams one ``{node, delta}`` update *after each stage
finishes* — too coarse to show the analyze stage's sub-agents working live. This module
lets deeper code (the Orchestrator's parallel sub-agents) push fine-grained events
(``agent_start`` / ``agent_done`` / ``agent_error`` / ``tool_call``) into the *current*
run's event log without threading a callback through every call site.

The emitter is held in a :class:`contextvars.ContextVar` so it is scoped to the thread
driving a run. Sub-agents fan out over a ``ThreadPoolExecutor``; contextvars do **not**
cross thread boundaries automatically, so callers must submit work with a copied context
(``contextvars.copy_context().run``). :func:`run_context` returns that copy for convenience.
"""
from __future__ import annotations

import contextvars
from typing import Any, Callable

_emitter: contextvars.ContextVar[Callable[[dict], None] | None] = contextvars.ContextVar(
    "imperium_run_emitter", default=None
)


def set_emitter(fn: Callable[[dict], None] | None):
    """Bind the current run's event sink; returns a token to reset with."""
    return _emitter.set(fn)


def reset_emitter(token) -> None:
    _emitter.reset(token)


def emit(event: dict[str, Any]) -> None:
    """Push an event to the active run's log, if any run is being driven."""
    fn = _emitter.get()
    if fn is not None:
        try:
            fn(event)
        except Exception:  # noqa: BLE001 — telemetry must never break the run
            pass


def run_context() -> contextvars.Context:
    """A snapshot of the current context, so pool workers keep the emitter bound.

    Usage: ``pool.submit(run_context().run, fn, *args)``.
    """
    return contextvars.copy_context()
