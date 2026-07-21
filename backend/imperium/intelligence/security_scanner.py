"""Security Scanner (TDD §4, PRD §10). Vulnerable patterns + CVE-bearing deps.

TODO(team): injection/auth-bypass pattern checks, secrets-in-code detection
(flag by reference only — never log secrets, PRD §14), dependency CVE lookup.
"""
from __future__ import annotations

from imperium.api.schemas import Finding


def scan(repo_path: str) -> list[Finding]:
    raise NotImplementedError("security scan — team task")
