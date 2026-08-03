"""Test-Generation & Verification Agent (TDD §8, PRD §10).

<<<<<<< HEAD
Runs TWICE: baseline (pre-change) then post-change, then diffs (PRD Step 10-12).
Edge cases derive from extracted business rules, not generic boilerplate.

Pipeline:
  1. Generate test code from business rules (Codestral via test_codegen role).
  2. Identify edge cases to cover (Nemotron via test_edgecase role).
  3. Execute tests via sandbox.runner against BASELINE code.
  4. Execute tests against POST-CHANGE code.
  5. Diff the two TestResult sets → behavioral diff report.
"""
from __future__ import annotations

import logging
import os
import tempfile
=======
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
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11

from imperium.agents.base import AgentContext, BaseAgent

log = logging.getLogger("imperium.agents.testing")

<<<<<<< HEAD
_CODEGEN_SYSTEM = (
    "You are an expert test engineer using Mistral Codestral. "
    "Given business rules and source code, write comprehensive pytest test cases that "
    "specifically exercise each stated rule. Include: normal path, boundary values, and "
    "error conditions. Output ONLY valid Python pytest code."
)

_EDGECASE_SYSTEM = (
    "You are a senior QA architect. Given a list of business rules extracted from code, "
    "identify the most critical edge cases that could regress during a modernization. "
    "Focus on: boundary conditions, state transitions, implicit invariants, and "
    "concurrency/ordering assumptions. "
    "Return JSON array: [{\"rule\": \"...\", \"edge_case\": \"...\", \"risk\": \"high|medium|low\"}]"
)
=======
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
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11


class TestingAgent(BaseAgent):
    name = "testing"
    # Two roles: write test code vs reason about edge cases (llm/routing.py)
    role_codegen = "test_codegen"    # → Mistral Codestral
    role_edgecase = "test_edgecase"  # → Nemotron

<<<<<<< HEAD
    # Required by BaseAgent ABC — delegates to run()
    role = "test_codegen"

    def run(self, ctx: AgentContext) -> dict:
        """Generate tests, execute baseline + post-change, return results."""
        repository_id = ctx.repository_id
        repo_path = ctx.repo_path

        if not repo_path:
            log.warning("TestingAgent: no repo_path for %s", repository_id)
            return {"baseline": {}, "post_change": {}, "behavioral_diff": {}}

        # 1. Gather business rules for edge-case generation
        rules = self._fetch_rules(repository_id)

        # 2. Identify high-risk edge cases
        edge_cases = self._identify_edge_cases(rules)

        # 3. Generate test code
        test_code = self._generate_tests(repo_path, rules, edge_cases)

        # 4. Write test file to repo
        test_file = self._write_test_file(repo_path, test_code)

        # 5. Run baseline
        baseline_result = self._run_phase(repo_path, test_file, "baseline", repository_id)

        # 6. Run post-change (same code path; implementation agent may have changed files)
        post_result = self._run_phase(repo_path, test_file, "post_change", repository_id)

        # 7. Build behavioral diff
        diff_report = self.behavioral_diff(ctx, baseline_result, post_result)

        return {
            "edge_cases": edge_cases,
            "test_file": test_file,
            "baseline": baseline_result,
            "post_change": post_result,
            "behavioral_diff": diff_report,
        }

    def behavioral_diff(
        self,
        ctx: AgentContext,
        baseline: dict | None = None,
        post_change: dict | None = None,
    ) -> dict:
        """Compare baseline vs post-change results into an itemized risk report."""
        if baseline is None:
            baseline = self._fetch_phase_results(ctx.repository_id, "baseline")
        if post_change is None:
            post_change = self._fetch_phase_results(ctx.repository_id, "post_change")

        b_passed = baseline.get("passed", 0)
        b_failed = baseline.get("failed", 0)
        p_passed = post_change.get("passed", 0)
        p_failed = post_change.get("failed", 0)

        regression_count = max(0, b_passed - p_passed)
        new_failures = max(0, p_failed - b_failed)

        risk = "none"
        if regression_count > 0 or new_failures > 0:
            risk = "high" if (regression_count + new_failures) > 3 else "medium"

        return {
            "baseline_passed": b_passed,
            "baseline_failed": b_failed,
            "post_change_passed": p_passed,
            "post_change_failed": p_failed,
            "regressions": regression_count,
            "new_failures": new_failures,
            "risk": risk,
            "summary": (
                f"{regression_count} regression(s), {new_failures} new failure(s). "
                f"Risk level: {risk}."
            ),
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _fetch_rules(self, repository_id: str) -> list[dict]:
=======
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
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
        try:
            from imperium.rkb.store import get_business_rules, get_session

            session = get_session()
            try:
<<<<<<< HEAD
                rules = get_business_rules(session, repository_id)
                return [
                    {"statement": r.statement, "confidence": r.confidence, "locations": r.locations}
                    for r in rules[:30]
                ]
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not fetch rules for testing: %s", exc)
            return []

    def _identify_edge_cases(self, rules: list[dict]) -> list[dict]:
        if not rules:
            return []
        try:
            import json
            import re

            from imperium.llm.client import complete

            rule_text = "\n".join(
                f"- [{r['confidence']:.0%}] {r['statement']}" for r in rules[:20]
            )
            text = complete(self.role_edgecase, rule_text, system=_EDGECASE_SYSTEM)
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as exc:  # noqa: BLE001
            log.warning("Edge case identification failed: %s", exc)
        return []

    def _generate_tests(
        self, repo_path: str, rules: list[dict], edge_cases: list[dict]
    ) -> str:
        if not rules and not edge_cases:
            return "# No business rules found — no tests generated\n"

        rule_text = "\n".join(f"# Rule: {r['statement']}" for r in rules[:15])
        ec_text = "\n".join(
            f"# Edge case ({e.get('risk', '?')}): {e.get('edge_case', '')}"
            for e in edge_cases[:10]
        )

        # Sample a small representative file for context
        sample_code = self._sample_source(repo_path)

        prompt = (
            f"Business rules:\n{rule_text}\n\n"
            f"Critical edge cases:\n{ec_text}\n\n"
            f"Sample source code (context only):\n```\n{sample_code[:3000]}\n```\n\n"
            "Write pytest tests covering each rule and edge case:"
        )
        try:
            from imperium.llm.client import complete

            return complete(self.role_codegen, prompt, system=_CODEGEN_SYSTEM, temperature=0.1)
        except Exception as exc:  # noqa: BLE001
            log.warning("Test generation LLM failed: %s", exc)
            return f"# Test generation failed: {exc}\n"

    def _sample_source(self, repo_path: str) -> str:
        """Return source text from the first Python file found (for LLM context)."""
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in files:
                if fname.endswith(".py") and not fname.startswith("test_"):
                    fp = os.path.join(root, fname)
                    try:
                        with open(fp, encoding="utf-8", errors="ignore") as fh:
                            return fh.read(3000)
                    except OSError:
                        continue
        return ""

    def _write_test_file(self, repo_path: str, test_code: str) -> str:
        """Write generated test code to a temp file and return the path."""
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                prefix="imperium_test_",
                dir=repo_path,
                delete=False,
                encoding="utf-8",
            )
            tmp.write(test_code)
            tmp.close()
            return tmp.name
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not write test file: %s", exc)
            return ""

    def _run_phase(
        self, repo_path: str, test_file: str, phase: str, repository_id: str
    ) -> dict:
        """Execute tests via sandbox runner for a given phase."""
        if not test_file or not os.path.isfile(test_file):
            return {"phase": phase, "passed": 0, "failed": 0, "error": "no test file"}

        try:
            from imperium.sandbox.runner import run

            result = run(
                code_path=repo_path,
                test_command=f"pytest {test_file} -q --tb=short",
                phase=phase,
            )
            self._persist_result(repository_id, phase, result)
            return {
                "phase": phase,
                "exit_code": result.exit_code,
                "passed": result.passed,
                "failed": result.failed,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:1000],
            }
        except NotImplementedError:
            log.debug("Sandbox runner not yet implemented — using mock result")
            return {"phase": phase, "passed": 0, "failed": 0, "note": "sandbox not available"}
        except Exception as exc:  # noqa: BLE001
            log.warning("Sandbox run failed (%s): %s", phase, exc)
            return {"phase": phase, "passed": 0, "failed": 0, "error": str(exc)}

    def _persist_result(self, repository_id: str, phase: str, result) -> None:
=======
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
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
        try:
            from imperium.rkb.models import TestResult
            from imperium.rkb.store import get_session

            session = get_session()
            try:
<<<<<<< HEAD
                tr = TestResult(
                    repository_id=repository_id,
                    phase=phase,
                    dimension="behavior",
                    payload={
                        "exit_code": result.exit_code,
                        "passed": result.passed,
                        "failed": result.failed,
                        "stdout": result.stdout[:2000],
                        "stderr": result.stderr[:500],
                    },
                )
                session.add(tr)
                session.commit()
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("TestResult persist failed: %s", exc)

    def _fetch_phase_results(self, repository_id: str, phase: str) -> dict:
        try:
            from imperium.rkb.models import TestResult
            from imperium.rkb.store import get_session

            session = get_session()
            try:
                rows = (
                    session.query(TestResult)
                    .filter_by(repository_id=repository_id, phase=phase)
                    .order_by(TestResult.created_at.desc())
                    .limit(1)
                    .all()
                )
                if rows:
                    return rows[0].payload or {}
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not fetch %s results: %s", phase, exc)
        return {}
=======
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
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
