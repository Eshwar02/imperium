"""Sandbox runner (PRD §13, Step 10-11). Executes generated tests against baseline
and modified code inside an isolated, ephemeral container — the execution engine
behind the behavioral diff.

Safety (PRD §14): ``docker run --rm`` with ``--network none``, memory + CPU limits, a
wall-clock timeout, and no secret mounts; the container is destroyed after the run.
Degrades gracefully: if Docker is unavailable the runner returns a ``SandboxResult``
with a negative exit code instead of raising, so the Testing agent can adapt.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field

from imperium.config import get_settings

log = logging.getLogger("imperium.sandbox.runner")


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    passed: int = 0
    failed: int = 0
    artifacts: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and self.failed == 0


# pytest: "3 passed, 1 failed"; jest: "Tests: 1 failed, 3 passed"
import re  # noqa: E402

_PASSED = re.compile(r"(\d+)\s+passed", re.IGNORECASE)
_FAILED = re.compile(r"(\d+)\s+failed", re.IGNORECASE)
_ERRORS = re.compile(r"(\d+)\s+error", re.IGNORECASE)


def parse_test_output(text: str) -> tuple[int, int]:
    """Extract (passed, failed) counts from pytest/jest-style output."""
    passed = sum(int(m.group(1)) for m in _PASSED.finditer(text))
    failed = sum(int(m.group(1)) for m in _FAILED.finditer(text))
    failed += sum(int(m.group(1)) for m in _ERRORS.finditer(text))
    return passed, failed


def run(code_path: str, test_command: str, phase: str) -> SandboxResult:
    """Run ``test_command`` against code at ``code_path`` in an ephemeral container.

    phase: 'baseline' | 'post_change' — persisted on TestResult for the diff.
    """
    settings = get_settings()
    if shutil.which("docker") is None:
        log.warning("Docker not available; sandbox run skipped (phase=%s)", phase)
        return SandboxResult(exit_code=-1, stderr="docker unavailable")

    timeout = settings.sandbox_timeout_seconds
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "512m",
        "--cpus", "1",
        "--pids-limit", "256",
        "-v", f"{code_path}:/work:rw",
        "-w", "/work",
        settings.sandbox_image,
        "sh", "-c", test_command,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 10, check=False
        )
    except subprocess.TimeoutExpired:
        log.warning("Sandbox run timed out (phase=%s)", phase)
        return SandboxResult(exit_code=124, stderr="timeout")
    except Exception as exc:  # noqa: BLE001
        log.warning("Sandbox run failed to start (phase=%s): %s", phase, exc)
        return SandboxResult(exit_code=-1, stderr=str(exc)[:300])

    combined = f"{proc.stdout}\n{proc.stderr}"
    passed, failed = parse_test_output(combined)
    return SandboxResult(
        exit_code=proc.returncode,
        stdout=proc.stdout[-8000:],
        stderr=proc.stderr[-4000:],
        passed=passed,
        failed=failed,
        artifacts={"phase": phase},
    )
