"""Sandbox runner (PRD §13, Step 10-11). Executes generated tests against baseline
and modified code inside an isolated, ephemeral container — the execution engine
behind the behavioral diff.

Foundation: interface + result shape. Real Docker exec is TODO(team).
Safety (PRD §14): no network by default, resource + time limits, no host mounts of
secrets, container destroyed after run.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from imperium.config import get_settings


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    passed: int = 0
    failed: int = 0
    artifacts: dict = field(default_factory=dict)


def run(code_path: str, test_command: str, phase: str) -> SandboxResult:
    """Run `test_command` against code at `code_path` in an ephemeral container.

    phase: 'baseline' | 'post_change' — persisted on TestResult for the diff.
    TODO(team): docker run --rm --network none --memory/--cpus limits, timeout from
    settings.sandbox_timeout_seconds, parse test output into pass/fail counts.
    """
    _ = get_settings()  # settings.sandbox_image / sandbox_timeout_seconds
    raise NotImplementedError("docker sandbox execution — team task")
