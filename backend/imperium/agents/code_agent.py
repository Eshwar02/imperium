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

import json
import logging
import re
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

_PLAN_SYSTEM = (
    "You are a senior engineer producing a MULTI-FILE REFACTOR PLAN. Use the read-only "
    "tools (grep_code, find_definition, read_file, list_dir, search_memory, blast_radius) "
    "to locate EVERY file the request touches — callers, tests, and configuration, not "
    "just the obvious one. Do NOT edit anything.\n\n"
    "Respond with ONLY a JSON array of ordered steps; each step is an object: "
    '{"file": "<relative/path>", "action": "<short imperative>", "rationale": "<why>"}. '
    "Order steps so that files others depend on change before their dependents."
)


class CodeAgent(BaseAgent):
    name = "code"
    role = "coding"  # groq -> nemotron -> mistral

    def run(self, ctx: AgentContext) -> dict:
        """Run the coding task from ``ctx.scratch['instruction']``."""
        instruction = ctx.scratch.get("instruction", "")
        if not instruction:
            return {"applied": False, "summary": "No instruction provided.", "diff": ""}
        return self.run_task(
            ctx,
            instruction,
            plan=ctx.scratch.get("plan", True),
            test_command=ctx.scratch.get("test_command"),
            max_test_iters=ctx.scratch.get("max_test_iters", 2),
        )

    # ── planning (multi-file refactor plans) ────────────────────────────────────

    def plan_task(self, ctx: AgentContext, instruction: str) -> dict:
        """Produce a structured multi-file refactor plan without editing anything.

        Returns ``{"steps": [{file, action, rationale}, ...], "summary": <raw text>}``.
        """
        if not ctx.repo_path:
            return {"steps": [], "summary": "No repository checked out."}
        try:
            from imperium.agents.agent_factory import build_agent, run_agent
            from imperium.agents.code_tools import build_code_tools
            from imperium.agents.tools import build_tools

            readonly = [
                t for t in build_code_tools(ctx)
                if t.name in ("grep_code", "find_definition", "read_file", "list_dir")
            ]
            locate = [t for t in build_tools(ctx) if t.name in ("search_memory", "blast_radius")]
            agent = build_agent(self.role, _PLAN_SYSTEM, readonly + locate)
            raw = run_agent(agent, instruction)
        except Exception as exc:  # noqa: BLE001 — provider down / no keys
            log.warning("plan_task failed: %s", exc)
            return {"steps": [], "summary": f"Planning unavailable: {exc}"}
        return {"steps": self._parse_steps(raw), "summary": raw}

    # ── execution ───────────────────────────────────────────────────────────────

    def run_task(
        self,
        ctx: AgentContext,
        instruction: str,
        *,
        plan: bool = True,
        test_command: str | None = None,
        max_test_iters: int = 2,
    ) -> dict:
        """Locate + modify code for ``instruction`` on an isolated branch; return a diff.

        ``plan``: first compute a multi-file refactor plan and feed it to the editor.
        ``test_command``: after editing, run it and iterate on failures (see ``_test_loop``).
        """
        if not ctx.repo_path:
            return {"applied": False, "summary": "No repository checked out.", "diff": ""}

        repo, branch = self._checkout_isolated_branch(ctx.repo_path)

        plan_steps: list[dict] = []
        try:
            from imperium.agents.agent_factory import run_agent

            if plan:
                plan_steps = self.plan_task(ctx, instruction)["steps"]
            agent, _ = self._build_editing_agent(ctx)
            summary = run_agent(agent, self._with_plan(instruction, plan_steps))
        except Exception as exc:  # noqa: BLE001 — provider down / no keys
            log.warning("CodeAgent run failed: %s", exc)
            return {"applied": False, "summary": f"Coding agent unavailable: {exc}", "diff": "", "branch": branch}

        tests = self._test_loop(ctx, agent, test_command, max_test_iters) if test_command else None

        diff, files = self._commit_and_diff(repo, instruction)
        result = {
            "applied": bool(files),
            "summary": summary,
            "branch": branch,
            "files_changed": files,
            "diff": diff,
            "plan": plan_steps,
        }
        if tests is not None:
            result["tests"] = tests
        return result

    def stream_task(
        self,
        ctx: AgentContext,
        instruction: str,
        *,
        plan: bool = True,
        test_command: str | None = None,
        max_test_iters: int = 2,
    ):
        """Run a coding task, yielding live events (plan, tool calls/results, tests, diff).

        Generator of dicts: ``start`` → ``plan`` → ``tool_call``/``tool_result``/``message``
        → ``final`` → ``tests`` (if requested) → ``done`` (or ``error``).
        """
        if not ctx.repo_path:
            yield {"type": "error", "message": "No repository checked out."}
            return

        repo, branch = self._checkout_isolated_branch(ctx.repo_path)
        yield {"type": "start", "branch": branch, "instruction": instruction}

        plan_steps: list[dict] = []
        if plan:
            plan_steps = self.plan_task(ctx, instruction)["steps"]
            yield {"type": "plan", "steps": plan_steps}

        summary = ""
        try:
            from imperium.agents.agent_factory import run_agent_stream

            agent, _ = self._build_editing_agent(ctx)
            for ev in run_agent_stream(agent, self._with_plan(instruction, plan_steps)):
                if ev.get("type") == "final":
                    summary = ev.get("text", "")
                yield ev
        except Exception as exc:  # noqa: BLE001 — provider down / no keys
            log.warning("CodeAgent stream failed: %s", exc)
            yield {"type": "error", "message": f"Coding agent unavailable: {exc}", "branch": branch}
            return

        if test_command:
            tests = self._test_loop(ctx, agent, test_command, max_test_iters)
            yield {"type": "tests", "result": tests}

        diff, files = self._commit_and_diff(repo, instruction)
        yield {
            "type": "done",
            "applied": bool(files),
            "summary": summary,
            "branch": branch,
            "files_changed": files,
            "diff": diff,
        }

    # ── agent + plan/test helpers ───────────────────────────────────────────────

    def _build_editing_agent(self, ctx: AgentContext):
        """Build the code-editing agent (edit tools + read-only locate tools). Returns (agent, tools)."""
        from imperium.agents.agent_factory import build_agent
        from imperium.agents.code_tools import build_code_tools
        from imperium.agents.tools import build_tools

        tools = build_code_tools(ctx)
        locate = [t for t in build_tools(ctx) if t.name in ("search_memory", "blast_radius")]
        all_tools = tools + locate
        return build_agent(self.role, _CODE_SYSTEM, all_tools), all_tools

    def _test_loop(self, ctx: AgentContext, agent, test_command: str, max_iters: int) -> dict:
        """Run ``test_command``; on failure feed the output back to ``agent`` and retry.

        Iterates up to ``max_iters`` fix attempts. Returns a record of every attempt.
        """
        from imperium.agents.agent_factory import run_agent
        from imperium.agents.code_tools import run_test_command

        def _snapshot(res: dict) -> dict:
            return {k: res[k] for k in ("ok", "exit_code", "passed", "failed")}

        res = run_test_command(ctx.repo_path, test_command)
        attempts = [_snapshot(res)]
        iters = 0
        while not res["ok"] and iters < max_iters:
            iters += 1
            fix_msg = (
                f"The test command `{test_command}` failed:\n\n{res['output']}\n\n"
                "Locate the cause and fix it with edit_file/write_file. Change only what "
                "is needed to make the tests pass without breaking other behavior."
            )
            try:
                run_agent(agent, fix_msg)
            except Exception as exc:  # noqa: BLE001 — provider down mid-loop
                log.warning("test-fix iteration %d failed: %s", iters, exc)
                break
            res = run_test_command(ctx.repo_path, test_command)
            attempts.append(_snapshot(res))
        return {
            "command": test_command,
            "passed": res["ok"],
            "iterations": iters,
            "attempts": attempts,
        }

    @staticmethod
    def _with_plan(instruction: str, steps: list[dict]) -> str:
        """Prepend a rendered refactor plan to the instruction, if any steps exist."""
        if not steps:
            return instruction
        lines = [
            f"{i + 1}. [{s.get('file', '?')}] {s.get('action', '')} — {s.get('rationale', '')}"
            for i, s in enumerate(steps)
        ]
        return (
            f"{instruction}\n\nProposed multi-file plan (follow it, refining as you learn more):\n"
            + "\n".join(lines)
        )

    @staticmethod
    def _parse_steps(raw: str) -> list[dict]:
        """Extract the JSON array of plan steps from an LLM response.

        Tolerant of prose/fences and of double-encoding — some models return an array of
        JSON *strings* rather than objects, so each element is re-parsed when needed.
        """
        match = re.search(r"\[.*\]", raw or "", re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group())
        except (ValueError, TypeError):
            return []
        steps: list[dict] = []
        for item in data if isinstance(data, list) else []:
            if isinstance(item, str):  # double-encoded: element is a JSON object string
                try:
                    item = json.loads(item)
                except (ValueError, TypeError):
                    continue
            if isinstance(item, dict) and item.get("file"):
                steps.append(item)
        return steps

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
