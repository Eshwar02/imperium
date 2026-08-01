"""GraphAgent — a small, low-cost agent that lays out an agent run as a node graph.

The *topology* of a decomposition (root → one sub-task per file) is cheap to build
deterministically. Deciding **which sub-task depends on which** — the edges worth
drawing between nodes — is a judgement call, so a small/fast model (the ``graph`` role,
routed to the cheapest providers) infers those dependency edges from the plan steps.

Kept deliberately tiny: one non-tool completion, strict JSON out, and a deterministic
linear fallback so the graph always renders even with no API key or a bad response.
Consumed by the frontend's live agent graph (dashed, draggable edges); see
``docs/frontend-build-guide.md`` §7b.
"""
from __future__ import annotations

import json
import logging
import re

log = logging.getLogger("imperium.agents.graph_agent")

_SYSTEM = (
    "You lay out a multi-file refactor as a small dependency graph. Given ordered plan "
    "steps (each a file + action), decide which files must change BEFORE others (a file "
    "that others import/depend on comes first). Respond with ONLY a JSON array of edges: "
    '[{"source": "<file>", "target": "<file>", "label": "<why, ≤4 words>"}]. '
    "source/target must be file paths from the steps. An edge source→target means target "
    "depends on source. No prose, no code fences."
)


class GraphAgent:
    """Turn plan steps into ``{nodes, edges}`` with inferred dependency edges."""

    role = "graph"

    def layout(self, steps: list[dict]) -> dict:
        """Return ``{nodes, edges}``: a root node + one node per step, plus dep edges."""
        steps = [s for s in (steps or []) if s.get("file")]
        nodes = [{"id": "root", "label": "CodeAgent", "type": "root", "detail": "plan"}]
        for s in steps:
            nodes.append(
                {
                    "id": s["file"],
                    "label": s["file"],
                    "type": "task",
                    "detail": s.get("action", ""),
                }
            )
        files = [s["file"] for s in steps]
        edges = [
            {"source": "root", "target": f, "label": "", "kind": "contains", "style": "dashed"}
            for f in files
        ]
        edges += [
            {**e, "kind": "depends", "style": "dashed"}
            for e in self._dependency_edges(steps, set(files))
        ]
        return {"nodes": nodes, "edges": edges}

    # ── dependency inference ────────────────────────────────────────────────────

    def _dependency_edges(self, steps: list[dict], files: set[str]) -> list[dict]:
        """LLM-inferred dep edges; deterministic linear chain on any failure."""
        if len(steps) < 2:
            return []
        try:
            from imperium.llm.factory import build_runnable

            runnable = build_runnable(self.role, temperature=0.0)
            listing = "\n".join(
                f"{i + 1}. {s['file']} — {s.get('action', '')}" for i, s in enumerate(steps)
            )
            raw = runnable.invoke(
                [("system", _SYSTEM), ("user", f"Plan steps:\n{listing}")]
            )
            text = getattr(raw, "content", raw)
            edges = self._parse_edges(text if isinstance(text, str) else str(text), files)
            if edges:
                return edges
        except Exception as exc:  # noqa: BLE001 — provider down / no keys / bad JSON
            log.info("GraphAgent LLM layout unavailable, using linear fallback: %s", exc)
        return self._linear(steps)

    @staticmethod
    def _linear(steps: list[dict]) -> list[dict]:
        """Fallback: each step depends on the previous (plan order)."""
        return [
            {"source": steps[i]["file"], "target": steps[i + 1]["file"], "label": "then"}
            for i in range(len(steps) - 1)
        ]

    @staticmethod
    def _parse_edges(text: str, files: set[str]) -> list[dict]:
        """Extract the JSON edge array; keep only edges between known files."""
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return []
        try:
            arr = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
        out = []
        for e in arr if isinstance(arr, list) else []:
            src, tgt = e.get("source"), e.get("target")
            if src in files and tgt in files and src != tgt:
                out.append({"source": src, "target": tgt, "label": (e.get("label") or "")[:40]})
        return out
