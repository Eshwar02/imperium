"""Sandbox runner (PRD §13, Step 10-11). Executes generated tests against baseline
and modified code inside an isolated, ephemeral container — the execution engine
behind the behavioral diff.

Safety (PRD §14): no network by default, resource + time limits, no host mounts of
secrets, container destroyed after run.

Implementation:
  - Pulls `sandbox_image` from settings (default: python:3.12-slim).
  - Mounts `code_path` as read-only /workspace.
  - Runs `test_command` inside the container with no network, memory cap, and
    CPU quota enforced via Docker CLI flags.
  - Parses pytest output for pass/fail counts.
  - Returns SandboxResult.
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field

from imperium.config import get_settings

log = logging.getLogger("imperium.sandbox.runner")

# Pytest summary line: "3 passed, 1 failed in 0.42s"
_PYTEST_SUMMARY_RE = re.compile(
    r"(?:(\d+)\s+passed)?[,\s]*(?:(\d+)\s+failed)?[,\s]*(?:(\d+)\s+error(?:s)?)?",
    re.IGNORECASE,
)


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    passed: int = 0
    failed: int = 0
    artifacts: dict = field(default_factory=dict)


def _parse_pytest_output(stdout: str) -> tuple[int, int]:
    """Extract (passed, failed) counts from pytest -q output."""
    passed = 0
    failed = 0
    # Look for the summary line (last line with numbers)
    for line in reversed(stdout.splitlines()):
        m = _PYTEST_SUMMARY_RE.search(line)
        if m and (m.group(1) or m.group(2)):
            passed = int(m.group(1) or 0)
            failed = int(m.group(2) or 0) + int(m.group(3) or 0)
            return passed, failed
    return passed, failed


def run(code_path: str, test_command: str, phase: str) -> SandboxResult:
    """Run `test_command` against code at `code_path` in an ephemeral Docker container.

    phase: 'baseline' | 'post_change' — recorded on the TestResult for the diff.

    Container constraints:
      --network none          — no outbound network
      --memory 512m           — RAM cap
      --cpus 1.0              — CPU cap
      --rm                    — destroy container after exit
      -v code_path:/workspace:ro  — read-only source mount
      --workdir /workspace    — tests run inside the source tree
      --timeout (via settings) — wall-clock limit via `timeout` CLI prefix
    """
    settings = get_settings()
    image = settings.sandbox_image
    timeout_secs = settings.sandbox_timeout_seconds

    log.info("Sandbox [%s]: image=%s timeout=%ds cmd=%r", phase, image, timeout_secs, test_command)

    # Build docker command
    docker_cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "512m",
        "--cpus", "1.0",
        "-v", f"{code_path}:/workspace:ro",
        "--workdir", "/workspace",
        image,
        "sh", "-c",
        # Install test deps (if requirements-test.txt exists) then run the command
        f"pip install pytest --quiet --disable-pip-version-check 2>/dev/null; {test_command}",
    ]

    try:
        proc = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_secs,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        passed, failed = _parse_pytest_output(stdout)

        log.info(
            "Sandbox [%s] done: exit=%d passed=%d failed=%d",
            phase, proc.returncode, passed, failed,
        )
        return SandboxResult(
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            passed=passed,
            failed=failed,
        )

    except subprocess.TimeoutExpired:
        log.warning("Sandbox [%s] timed out after %ds", phase, timeout_secs)
        return SandboxResult(
            exit_code=124,  # timeout exit code convention
            stdout="",
            stderr=f"Sandbox timed out after {timeout_secs} seconds",
            passed=0,
            failed=0,
        )
    except FileNotFoundError:
        log.error("docker binary not found — sandbox execution unavailable")
        raise RuntimeError(
            "Docker is not installed or not on PATH. "
            "Install Docker to enable sandbox test execution."
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Sandbox [%s] failed: %s", phase, exc)
        return SandboxResult(
            exit_code=1,
            stdout="",
            stderr=str(exc),
            passed=0,
            failed=0,
        )
