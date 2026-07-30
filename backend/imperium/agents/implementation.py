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
import uuid

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

    def apply_changes(
        self, ctx: AgentContext, proposed_changes: list[dict], branch: str | None = None
    ) -> dict:
        """Apply approved edits in an **isolated git branch** — never touches main.

        Operates on the workspace clone at ``ctx.repo_path``. Writes each change's
        ``new_code``, commits with a message traceable to the changeset, and leaves the
        default branch untouched. Returns ``{applied, branch, files, commit}``.
        """
        if not ctx.repo_path or not proposed_changes:
            return {"applied": False, "reason": "no repo_path or no changes"}
        try:
            from git import Repo

            repo = Repo(ctx.repo_path)
        except Exception as exc:  # noqa: BLE001 — not a git repo / gitpython missing
            log.warning("apply_changes: cannot open git repo: %s", exc)
            return {"applied": False, "reason": f"not a git repo: {exc}"}

        branch = branch or f"imperium/auto-{uuid.uuid4().hex[:8]}"
        try:
            repo.git.checkout("-b", branch)  # new branch off current HEAD; main untouched
            written: list[str] = []
            for change in proposed_changes:
                rel = change.get("file_path")
                code = change.get("new_code")
                if not rel or code is None:
                    continue
                full = os.path.normpath(os.path.join(ctx.repo_path, rel))
                if not full.startswith(os.path.normpath(ctx.repo_path)):
                    continue  # refuse path traversal
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(code)
                written.append(rel)
            if not written:
                return {"applied": False, "reason": "no writable changes", "branch": branch}
            repo.index.add(written)
            commit = repo.index.commit(
                f"Imperium: apply approved transformation ({len(written)} files)\n\n"
                f"Changeset: {ctx.scratch.get('changeset_id', 'auto')}"
            )
            return {"applied": True, "branch": branch, "files": written, "commit": commit.hexsha}
        except Exception as exc:  # noqa: BLE001
            log.warning("apply_changes failed: %s", exc)
            return {"applied": False, "reason": str(exc)[:200], "branch": branch}

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
