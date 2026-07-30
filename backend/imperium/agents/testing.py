"""Test-Generation & Verification Agent (TDD §8, PRD §10).

Two LLM roles by design: ``test_edgecase`` (Nemotron) reasons about *which* edge cases
matter — derived from the extracted business rules, not generic boilerplate — and
``test_codegen`` (Mistral Codestral) writes the test code. ``behavioral_diff`` then
compares baseline vs post-change ``TestResult`` rows per dimension into the itemized
risk report that is Imperium's core evidence artifact.
"""
from __future__ import annotations

import json
import logging
import re

from imperium.agents.base import AgentContext, BaseAgent

log = logging.getLogger("imperium.agents.testing")

_EDGECASE_SYSTEM = (
    "You are a test architect. Given a module's business rules, enumerate the edge "
    "cases that most threaten correctness or safety. Respond with ONLY a JSON array of "
    'strings: ["edge case description", ...]. Prioritize rule-violating inputs, '
    "boundary values, and security-sensitive paths."
)
_CODEGEN_SYSTEM = (
    "You are a senior engineer writing pytest tests. Given edge cases, write runnable, "
    "isolated test functions. Return ONLY code, no prose, no fences."
)
_DIMENSIONS = ("security", "dataflow", "load", "perf", "behavior")


class TestingAgent(BaseAgent):
    name = "testing"
    # Two roles: write test code vs reason about edge cases (llm/routing.py)
    role_codegen = "test_codegen"    # → Mistral Codestral
    role_edgecase = "test_edgecase"  # → Nemotron

    def run(self, ctx: AgentContext) -> dict:
        """Derive edge cases from business rules, then generate test code for them."""
        rules = self._fetch_rules(ctx.repository_id)
        if not rules:
            log.info("No business rules to ground tests for %s", ctx.repository_id)
            return {"edge_cases": [], "tests": ""}

        edge_cases = self._reason_edge_cases(rules)
        if not edge_cases:
            return {"edge_cases": [], "tests": ""}

        tests = self._write_tests(edge_cases)
        return {"edge_cases": edge_cases, "tests": tests}

    def run_verification(self, ctx: AgentContext, test_command: str = "pytest -q") -> dict:
        """Execute tests in the sandbox for baseline + post_change and persist results.

        ``ctx.scratch`` may carry ``baseline_path`` / ``post_change_path`` (defaulting to
        ``ctx.repo_path``). Runs are isolated + ephemeral (see ``sandbox.runner``);
        results become ``TestResult`` rows the behavioral diff consumes.
        """
        from imperium.sandbox.runner import run as sandbox_run

        phases = {
            "baseline": ctx.scratch.get("baseline_path", ctx.repo_path),
            "post_change": ctx.scratch.get("post_change_path", ctx.repo_path),
        }
        outcomes: dict[str, dict] = {}
        for phase, path in phases.items():
            if not path:
                continue
            result = sandbox_run(path, test_command, phase)
            payload = {
                "passed": result.ok,
                "pass_count": result.passed,
                "fail_count": result.failed,
                "exit_code": result.exit_code,
            }
            outcomes[phase] = payload
            self._persist_result(ctx.repository_id, phase, "behavior", payload)
        return {"phases": outcomes}

    def _persist_result(self, repository_id: str, phase: str, dimension: str, payload: dict) -> None:
        try:
            from imperium.rkb.store import get_session, save_test_result

            session = get_session()
            try:
                save_test_result(session, repository_id, phase, dimension, payload)
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.debug("persist test result failed: %s", exc)

    def behavioral_diff(self, ctx: AgentContext) -> dict:
        """Compare baseline vs post-change results into an itemized per-dimension report."""
        baseline, post = self._fetch_results(ctx.repository_id)
        report: list[dict] = []
        regressions = 0
        for dim in _DIMENSIONS:
            b = baseline.get(dim)
            p = post.get(dim)
            if b is None and p is None:
                continue
            changed = b != p
            is_regression = changed and self._is_regression(b, p)
            regressions += int(is_regression)
            report.append(
                {
                    "dimension": dim,
                    "baseline": b,
                    "post_change": p,
                    "changed": changed,
                    "regression": is_regression,
                }
            )
        return {"report": report, "regressions": regressions, "safe": regressions == 0}

    # ── helpers ───────────────────────────────────────────────────────────────

    def _fetch_rules(self, repository_id: str) -> list:
        try:
            from imperium.rkb.store import get_business_rules, get_session

            session = get_session()
            try:
                return get_business_rules(session, repository_id)
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.debug("rule fetch failed: %s", exc)
            return []

    def _reason_edge_cases(self, rules: list) -> list[str]:
        try:
            from imperium.llm.client import complete

            rule_text = "\n".join(f"- {r.statement}" for r in rules[:40])
            text = complete(self.role_edgecase, rule_text, system=_EDGECASE_SYSTEM, temperature=0.3)
            match = re.search(r"\[.*\]", text or "", re.DOTALL)
            if match:
                cases = json.loads(match.group())
                return [c for c in cases if isinstance(c, str)][:30]
        except Exception as exc:  # noqa: BLE001
            log.warning("Edge-case reasoning failed: %s", exc)
        return []

    def _write_tests(self, edge_cases: list[str]) -> str:
        try:
            from imperium.llm.client import complete

            prompt = "Write pytest tests for these edge cases:\n" + "\n".join(
                f"- {c}" for c in edge_cases
            )
            return complete(self.role_codegen, prompt, system=_CODEGEN_SYSTEM, temperature=0.1) or ""
        except Exception as exc:  # noqa: BLE001
            log.warning("Test codegen failed: %s", exc)
            return ""

    def _fetch_results(self, repository_id: str) -> tuple[dict, dict]:
        """Return ({dimension: payload}, {dimension: payload}) for baseline/post_change."""
        try:
            from imperium.rkb.models import TestResult
            from imperium.rkb.store import get_session

            session = get_session()
            try:
                rows = session.query(TestResult).filter_by(repository_id=repository_id).all()
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.debug("test result fetch failed: %s", exc)
            return {}, {}

        baseline: dict = {}
        post: dict = {}
        for row in rows:
            (baseline if row.phase == "baseline" else post)[row.dimension] = row.payload
        return baseline, post

    @staticmethod
    def _is_regression(baseline, post) -> bool:
        """A dimension regressed if it was passing/ok in baseline and no longer is."""
        if not isinstance(baseline, dict) or not isinstance(post, dict):
            return baseline is not None and post != baseline
        was_ok = baseline.get("passed", baseline.get("ok", True))
        now_ok = post.get("passed", post.get("ok", True))
        return bool(was_ok) and not bool(now_ok)
