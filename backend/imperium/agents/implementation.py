"""Implementation Agent (TDD §8, §9). Generates the code changes for an approved
transformation (PRD Step 8) on the ``implementation`` role (Mistral Codestral).

Safety first (PRD §14): this agent **never writes to disk or touches main**. It
produces *proposed* edits — modernized file contents + a unified diff — as artifacts
the human-gated pipeline can review (Gate B) and later apply in an isolated branch.

Targets come from ``ctx.scratch['target_files']`` if provided, otherwise the files in
the repository's most recent changeset manifest.
"""
from __future__ import annotations

import difflib
import logging
import os

from imperium.agents.base import AgentContext, BaseAgent

log = logging.getLogger("imperium.agents.implementation")

_MAX_FILES = 20
_MAX_FILE_BYTES = 20_000
_DEFAULT_INSTRUCTIONS = (
    "Modernize this file (idioms, deprecated APIs, clarity, safety) while preserving "
    "every existing business rule and externally observable behavior."
)
_IMPL_SYSTEM = (
    "You are a senior engineer performing a safe modernization. Return ONLY the full "
    "updated file contents, no prose, no code fences. Preserve behavior exactly."
)


class ImplementationAgent(BaseAgent):
    name = "implementation"
    role = "implementation"  # → Mistral Codestral

    def run(self, ctx: AgentContext) -> dict:
        """Produce proposed (unapplied) edits for the target files."""
        if not ctx.repo_path:
            return {"proposed_changes": []}

        files = self._target_files(ctx)
        instructions = ctx.scratch.get("instructions", _DEFAULT_INSTRUCTIONS)

        changes: list[dict] = []
        for rel_path in files[:_MAX_FILES]:
            old_code = self._read(ctx.repo_path, rel_path)
            if old_code is None:
                continue
            new_code = self._generate(rel_path, old_code, instructions)
            if not new_code or new_code == old_code:
                continue
            diff = "".join(
                difflib.unified_diff(
                    old_code.splitlines(keepends=True),
                    new_code.splitlines(keepends=True),
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                )
            )
            changes.append({"file_path": rel_path, "new_code": new_code, "diff": diff})

        return {"proposed_changes": changes}

    # ── helpers ───────────────────────────────────────────────────────────────

    def _target_files(self, ctx: AgentContext) -> list[str]:
        targets = ctx.scratch.get("target_files")
        if targets:
            return list(targets)
        try:
            from imperium.rkb.store import get_changesets, get_session

            session = get_session()
            try:
                changesets = get_changesets(session, ctx.repository_id)
                if changesets:
                    latest = changesets[-1]
                    return [f.file_path for f in getattr(latest, "files", [])]
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.debug("changeset lookup failed: %s", exc)
        return []

    def _read(self, repo_path: str, rel_path: str) -> str | None:
        full = os.path.normpath(os.path.join(repo_path, rel_path))
        if not full.startswith(os.path.normpath(repo_path)) or not os.path.isfile(full):
            return None
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                return fh.read(_MAX_FILE_BYTES)
        except OSError:
            return None

    def _generate(self, rel_path: str, old_code: str, instructions: str) -> str | None:
        try:
            from imperium.llm.client import complete

            prompt = f"File: {rel_path}\nInstructions: {instructions}\n\n{old_code}"
            return complete(self.role, prompt, system=_IMPL_SYSTEM, temperature=0.1)
        except Exception as exc:  # noqa: BLE001
            log.warning("Implementation generation failed for %s: %s", rel_path, exc)
            return None
