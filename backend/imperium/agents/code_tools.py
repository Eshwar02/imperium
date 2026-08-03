"""Code navigation + precise editing tools — the Claude-Code-style toolset.

These give a coding agent the same core loop Claude Code uses: **grep/find/read** to
locate the exact relevant code, then **edit/write** to change it precisely. Editing is
exact-match (like Claude Code's Edit): the old snippet must appear exactly once, so the
agent changes the right place or is told to disambiguate.

All operations are bound to the run's ``repo_path`` and refuse to escape it. Writes land
on the workspace clone (reviewable via git), never outside the repository root.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess

from langchain_core.tools import BaseTool, tool

from imperium.agents.base import AgentContext

log = logging.getLogger("imperium.agents.code_tools")

_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".mypy_cache"}
_SOURCE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java", ".rs", ".php", ".c", ".cpp", ".h", ".cs", ".md", ".txt", ".json", ".yaml", ".yml", ".toml"}
_MAX_MATCHES = 100
_MAX_READ_BYTES = 40_000
_TEST_TIMEOUT = 300
_DEFAULT_TEST_COMMAND = "pytest -q"


def run_test_command(repo_path: str, command: str = _DEFAULT_TEST_COMMAND) -> dict:
    """Run a shell test ``command`` inside ``repo_path`` and return a parsed result.

    Returns ``{ok, exit_code, passed, failed, output}``. Never raises: a timeout or
    startup failure degrades to a non-ok result so the caller (agent / test loop) can
    read the output and react. Pass/fail counts reuse the pytest/jest parser from the
    sandbox runner.
    """
    from imperium.sandbox.runner import parse_test_output

    if not repo_path:
        return {"ok": False, "exit_code": -1, "passed": 0, "failed": 0, "output": "No repository checked out."}
    try:
        proc = subprocess.run(
            command, shell=True, cwd=repo_path,
            capture_output=True, text=True, timeout=_TEST_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": 124, "passed": 0, "failed": 0, "output": "timeout"}
    except Exception as exc:  # noqa: BLE001 — command may be malformed / shell missing
        return {"ok": False, "exit_code": -1, "passed": 0, "failed": 0, "output": str(exc)[:500]}
    combined = f"{proc.stdout}\n{proc.stderr}"
    passed, failed = parse_test_output(combined)
    return {
        "ok": proc.returncode == 0 and failed == 0,
        "exit_code": proc.returncode,
        "passed": passed,
        "failed": failed,
        "output": combined[-6000:],
    }


def _safe_path(repo_path: str, rel: str) -> str | None:
    """Resolve ``rel`` under ``repo_path``; return None if it escapes the root."""
    full = os.path.normpath(os.path.join(repo_path, rel))
    root = os.path.normpath(repo_path)
    return full if full == root or full.startswith(root + os.sep) else None


def _iter_files(repo_path: str):
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() in _SOURCE_EXTS:
                yield os.path.join(root, name)


def build_code_tools(ctx: AgentContext) -> list[BaseTool]:
    """Return the navigation + editing tools bound to this run's repository."""
    repo_path = ctx.repo_path

    @tool
    def grep_code(pattern: str) -> str:
        """Search the repository for a regex pattern. Returns file:line: match snippets."""
        if not repo_path:
            return "No repository checked out."
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return f"Invalid regex: {exc}"
        hits: list[str] = []
        for fpath in _iter_files(repo_path):
            try:
                with open(fpath, encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if rx.search(line):
                            rel = os.path.relpath(fpath, repo_path)
                            hits.append(f"{rel}:{i}: {line.strip()[:200]}")
                            if len(hits) >= _MAX_MATCHES:
                                return "\n".join(hits) + "\n… (truncated)"
            except OSError:
                continue
        return "\n".join(hits) if hits else "No matches."

    @tool
    def find_definition(name: str) -> str:
        """Find where a function/class/method named `name` is defined."""
        if not repo_path:
            return "No repository checked out."
        rx = re.compile(rf"\b(def|class|func|function|type|interface)\s+{re.escape(name)}\b")
        hits: list[str] = []
        for fpath in _iter_files(repo_path):
            try:
                with open(fpath, encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if rx.search(line):
                            hits.append(f"{os.path.relpath(fpath, repo_path)}:{i}: {line.strip()[:200]}")
            except OSError:
                continue
        return "\n".join(hits) if hits else f"No definition found for '{name}'."

    @tool
    def list_dir(relative_path: str = ".") -> str:
        """List files and subdirectories under a path relative to the repo root."""
        if not repo_path:
            return "No repository checked out."
        full = _safe_path(repo_path, relative_path)
        if full is None or not os.path.isdir(full):
            return f"Not a directory: {relative_path}"
        entries = sorted(os.listdir(full))
        out = []
        for e in entries:
            if e in _SKIP_DIRS:
                continue
            marker = "/" if os.path.isdir(os.path.join(full, e)) else ""
            out.append(e + marker)
        return "\n".join(out) if out else "(empty)"

    @tool
    def read_file(relative_path: str, start_line: int = 1, end_line: int = 0) -> str:
        """Read a file (optionally a line range) with line numbers, for precise edits."""
        if not repo_path:
            return "No repository checked out."
        full = _safe_path(repo_path, relative_path)
        if full is None or not os.path.isfile(full):
            return f"No such file: {relative_path}"
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as exc:
            return f"Could not read {relative_path}: {exc}"
        end = end_line if end_line and end_line >= start_line else len(lines)
        selected = lines[max(0, start_line - 1):end]
        numbered = [f"{start_line + i}\t{ln.rstrip(chr(10))}" for i, ln in enumerate(selected)]
        body = "\n".join(numbered)
        return body[:_MAX_READ_BYTES] + ("\n… (truncated)" if len(body) > _MAX_READ_BYTES else "")

    @tool
    def edit_file(relative_path: str, old_string: str, new_string: str) -> str:
        """Replace an exact snippet in a file. `old_string` must appear exactly once.

        This is the precise-edit primitive: include enough surrounding context in
        `old_string` to make it unique, or you'll be asked to disambiguate.
        """
        if not repo_path:
            return "No repository checked out."
        full = _safe_path(repo_path, relative_path)
        if full is None or not os.path.isfile(full):
            return f"No such file: {relative_path}"
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError as exc:
            return f"Could not read {relative_path}: {exc}"
        count = content.count(old_string)
        if count == 0:
            return "old_string not found. Read the file and copy the exact text."
        if count > 1:
            return f"old_string matches {count} places. Add surrounding context to make it unique."
        updated = content.replace(old_string, new_string, 1)
        try:
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(updated)
        except OSError as exc:
            return f"Could not write {relative_path}: {exc}"
        return f"Edited {relative_path} (1 replacement)."

    @tool
    def write_file(relative_path: str, content: str) -> str:
        """Create or overwrite a file with `content` (relative to the repo root)."""
        if not repo_path:
            return "No repository checked out."
        full = _safe_path(repo_path, relative_path)
        if full is None:
            return "Refused: path escapes the repository root."
        try:
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as exc:
            return f"Could not write {relative_path}: {exc}"
        return f"Wrote {relative_path} ({len(content)} bytes)."

    @tool
    def run_tests(command: str = _DEFAULT_TEST_COMMAND) -> str:
        """Run the repository's test command to verify your changes. Defaults to `pytest -q`.

        Use this after editing to confirm the change works and nothing regressed. Returns
        PASSED/FAILED with pass/fail counts and the tail of the test output.
        """
        if not repo_path:
            return "No repository checked out."
        res = run_test_command(repo_path, command)
        status = "PASSED" if res["ok"] else "FAILED"
        return (
            f"{status} (exit={res['exit_code']}, passed={res['passed']}, failed={res['failed']})\n"
            + res["output"]
        )

    return [grep_code, find_definition, list_dir, read_file, edit_file, write_file, run_tests]
