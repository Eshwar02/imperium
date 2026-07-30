"""CodeAgent — a Claude-Code-style coding agent.

Given a natural-language instruction ("rename X", "add validation to the login route",
"fix the off-by-one in paginate"), it *locates* the exact relevant code with grep /
find_definition / read_file (plus semantic memory + the call graph), then makes *minimal
precise edits* with edit_file / write_file — the same retrieve-then-modify loop Claude
Code uses.

Safety: all work happens on an **isolated git branch** of the workspace clone; the
default branch is never touched. The agent's edits are committed there and returned as a
diff for human review (Gate B).
"""
from __future__ import annotations

import logging
import uuid

from imperium.agents.base import AgentContext, BaseAgent

log = logging.getLogger("imperium.agents.code_agent")

_CODE_SYSTEM = (
    "You are an expert software engineer working directly in a repository, like a "
    "senior developer pair-programming. Your job: fulfill the user's request by editing "
    "the codebase precisely.\n\n"
    "Workflow — always in this order:\n"
    "1. LOCATE: use grep_code, find_definition, list_dir, and search_memory to find the "
    "exact file(s) and lines relevant to the request. Never guess a path.\n"
    "2. READ: read_file the relevant region (with line numbers) before changing it.\n"
    "3. EDIT: make the smallest correct change with edit_file (exact-match) or write_file "
    "for new files. Preserve existing style and behavior not in scope.\n"
    "4. VERIFY: read_file the changed region again to confirm the edit is correct.\n\n"
    "Rules: change only what the request requires; keep edits minimal and surgical; if the "
    "request is ambiguous, make the most reasonable interpretation and state it. When done, "
    "give a short summary of exactly what you changed and why."
)


class CodeAgent(BaseAgent):
    name = "code"
    role = "coding"  # groq -> nemotron -> mistral

    def run(self, ctx: AgentContext) -> dict:
        """Run the coding task from ``ctx.scratch['instruction']``."""
        instruction = ctx.scratch.get("instruction", "")
        if not instruction:
            return {"applied": False, "summary": "No instruction provided.", "diff": ""}
        return self.run_task(ctx, instruction)

    def run_task(self, ctx: AgentContext, instruction: str) -> dict:
        """Locate + modify code for ``instruction`` on an isolated branch; return a diff."""
        if not ctx.repo_path:
            return {"applied": False, "summary": "No repository checked out.", "diff": ""}

        repo, branch = self._checkout_isolated_branch(ctx.repo_path)

        try:
            from imperium.agents.agent_factory import build_agent, run_agent
            from imperium.agents.code_tools import build_code_tools
            from imperium.agents.tools import build_tools

            # code-editing tools + a couple of read-only locate tools (semantic + graph)
            tools = build_code_tools(ctx)
            locate = [t for t in build_tools(ctx) if t.name in ("search_memory", "blast_radius")]
            agent = build_agent(self.role, _CODE_SYSTEM, tools + locate)
            summary = run_agent(agent, instruction)
        except Exception as exc:  # noqa: BLE001 — provider down / no keys
            log.warning("CodeAgent run failed: %s", exc)
            return {"applied": False, "summary": f"Coding agent unavailable: {exc}", "diff": "", "branch": branch}

        diff, files = self._commit_and_diff(repo, instruction)
        return {
            "applied": bool(files),
            "summary": summary,
            "branch": branch,
            "files_changed": files,
            "diff": diff,
        }

    # ── git helpers ───────────────────────────────────────────────────────────

    def _checkout_isolated_branch(self, repo_path: str):
        """Create + check out an isolated branch. Returns (repo_or_None, branch_name)."""
        branch = f"imperium/code-{uuid.uuid4().hex[:8]}"
        try:
            from git import Repo

            repo = Repo(repo_path)
            repo.git.checkout("-b", branch)  # off current HEAD; default branch untouched
            return repo, branch
        except Exception as exc:  # noqa: BLE001 — not a git repo / gitpython missing
            log.debug("isolated branch unavailable (%s); editing workspace directly", exc)
            return None, branch

    def _commit_and_diff(self, repo, instruction: str) -> tuple[str, list[str]]:
        """Stage + commit all changes; return (unified_diff, changed_files)."""
        if repo is None:
            return "", []
        try:
            changed = [item.a_path for item in repo.index.diff(None)] + repo.untracked_files
            if not changed:
                return "", []
            repo.git.add(A=True)
            diff = repo.git.diff("HEAD")
            repo.index.commit(f"Imperium code change: {instruction[:72]}")
            return diff, changed
        except Exception as exc:  # noqa: BLE001
            log.warning("commit/diff failed: %s", exc)
            return "", []
