"""Self-healing layer. The system catches its own failures, diagnoses them, and
auto-remediates — silently, without surfacing errors to the user.

Design & safety boundary:
  A dedicated **healing agent** diagnoses each failure and chooses a recovery action
  from a *bounded, safe set* — retry, reconnect, switch provider, reduce scope, or skip.
  It deliberately does **not** rewrite the running system's source code (that would be
  unauditable and unsafe). Diagnosis is LLM-assisted (role ``healing``) but always falls
  back to a deterministic classifier, so healing never depends on the thing that broke.

  Failures are recorded to an internal ``IncidentLog`` (operator-visible only) and the
  wrapped call returns a safe default instead of raising — so a fault heals or degrades
  in the background rather than reaching the user.

Usage:
    @self_healing("ingestion.parse", default=[])
    def parse(...): ...

    result = heal_call("agent.research", agent.run, ctx, default={"findings": []})
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("imperium.core.healing")


class RecoveryAction(str, Enum):
    RETRY = "retry"                  # transient — try again (with backoff)
    RECONNECT = "reconnect"          # a backing service dropped — re-establish it
    SWITCH_PROVIDER = "switch_provider"  # LLM/provider fault — rotate providers
    REDUCE_SCOPE = "reduce_scope"    # payload/context too big — shrink and retry
    SKIP = "skip"                    # this unit is bad — skip and degrade
    ABORT = "abort"                  # unrecoverable — give up (still silent)


@dataclass
class Incident:
    id: str
    component: str
    error: str
    action: RecoveryAction
    attempt: int
    resolved: bool = False
    ts: float = field(default_factory=time.time)


class IncidentLog:
    """Bounded, thread-safe record of self-healing incidents (operator-only)."""

    def __init__(self, capacity: int = 500) -> None:
        self._items: deque[Incident] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def record(self, incident: Incident) -> None:
        with self._lock:
            self._items.append(incident)
        log.info(
            "self-heal component=%s action=%s attempt=%d resolved=%s err=%s",
            incident.component, incident.action.value, incident.attempt,
            incident.resolved, incident.error[:160],
        )

    def recent(self, limit: int = 100) -> list[dict]:
        with self._lock:
            return [i.__dict__ | {"action": i.action.value} for i in list(self._items)[-limit:]]


incident_log = IncidentLog()

# Components register recovery hooks (e.g. reset a DB session / graph driver / cache).
_recovery_hooks: dict[str, Callable[[], None]] = {}


def register_recovery_hook(component_prefix: str, hook: Callable[[], None]) -> None:
    """Register a side-effecting recovery (e.g. reconnect) for components under a prefix."""
    _recovery_hooks[component_prefix] = hook


def _run_hooks(component: str) -> None:
    for prefix, hook in _recovery_hooks.items():
        if component.startswith(prefix):
            try:
                hook()
            except Exception as exc:  # noqa: BLE001 — healing must never raise
                log.debug("recovery hook %s failed: %s", prefix, exc)


# ── deterministic diagnosis (the always-available fallback) ────────────────────

def classify_error(exc: Exception) -> RecoveryAction:
    """Map an exception to a recovery action without any LLM."""
    msg = f"{type(exc).__name__}: {exc}".lower()
    if isinstance(exc, ConnectionError) or "connection" in msg or "refused" in msg or "unreachable" in msg:
        return RecoveryAction.RECONNECT
    if isinstance(exc, TimeoutError) or "timeout" in msg or "timed out" in msg:
        return RecoveryAction.RETRY
    if "rate limit" in msg or "429" in msg or "quota" in msg or "overloaded" in msg:
        return RecoveryAction.SWITCH_PROVIDER
    if "context length" in msg or "maximum context" in msg or "too large" in msg or "token" in msg:
        return RecoveryAction.REDUCE_SCOPE
    if isinstance(exc, (ValueError, KeyError, TypeError)) or "json" in msg or "parse" in msg:
        return RecoveryAction.SKIP
    return RecoveryAction.RETRY


class HealingAgent:
    """Diagnoses failures. LLM-assisted (role ``healing``) with deterministic fallback."""

    role = "healing"

    def diagnose(self, exc: Exception, context: dict | None = None) -> RecoveryAction:
        det = classify_error(exc)
        # Only consult the LLM for ambiguous cases; never let it break healing.
        if det is not RecoveryAction.RETRY:
            return det
        try:
            from imperium.llm.client import complete

            prompt = (
                f"A component failed.\nComponent: {(context or {}).get('component', '?')}\n"
                f"Error: {type(exc).__name__}: {exc}\n"
                f"Choose ONE recovery action: {', '.join(a.value for a in RecoveryAction)}.\n"
                "Answer with only the action word."
            )
            answer = complete(self.role, prompt, temperature=0.0).strip().lower()
            for action in RecoveryAction:
                if action.value in answer:
                    return action
        except Exception as exc2:  # noqa: BLE001 — fall back to deterministic
            log.debug("healing LLM unavailable: %s", exc2)
        return det


healing_agent = HealingAgent()


# ── the wrapper ────────────────────────────────────────────────────────────────

def heal_call(
    component: str,
    fn: Callable,
    *args,
    retries: int = 2,
    default: Any = None,
    backoff: float = 0.0,
    **kwargs,
) -> Any:
    """Call ``fn`` with self-healing. On failure, diagnose → remediate → retry/skip.

    Returns ``fn``'s result, or ``default`` if it cannot be healed. Never raises.
    """
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — this is the healing boundary
            action = healing_agent.diagnose(exc, {"component": component, "attempt": attempt})
            recoverable = action in (
                RecoveryAction.RETRY,
                RecoveryAction.RECONNECT,
                RecoveryAction.SWITCH_PROVIDER,
                RecoveryAction.REDUCE_SCOPE,
            )
            resolved = recoverable and attempt < retries
            incident_log.record(
                Incident(uuid.uuid4().hex, component, f"{type(exc).__name__}: {exc}", action, attempt, resolved)
            )
            if not resolved:
                return default  # skip / abort / retries exhausted — degrade silently

            if action in (RecoveryAction.RECONNECT, RecoveryAction.SWITCH_PROVIDER):
                _run_hooks(component)
            if backoff:
                time.sleep(backoff * (2 ** attempt))
            attempt += 1


def self_healing(component: str, default: Any = None, retries: int = 2, backoff: float = 0.0):
    """Decorator form of ``heal_call``."""

    def decorator(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            return heal_call(component, fn, *args, retries=retries, default=default, backoff=backoff, **kwargs)

        wrapper.__name__ = getattr(fn, "__name__", "healed")
        wrapper.__doc__ = fn.__doc__
        return wrapper

    return decorator


def get_incidents(limit: int = 100) -> list[dict]:
    """Operator-only view of recent self-healing incidents."""
    return incident_log.recent(limit)


def _default_recovery() -> None:
    """Baseline remediation applied on reconnect/switch-provider for any component.

    Drops cached LLM model instances so the next attempt rebuilds them (rotating past a
    provider that started failing) and resets the Neo4j driver if it exposes a reset.
    """
    try:
        from imperium.llm.factory import clear_cache

        clear_cache()
    except Exception:  # noqa: BLE001
        pass
    try:
        import imperium.rkb.graph as graph

        if hasattr(graph, "reset_driver"):
            graph.reset_driver()
    except Exception:  # noqa: BLE001
        pass


register_recovery_hook("", _default_recovery)
