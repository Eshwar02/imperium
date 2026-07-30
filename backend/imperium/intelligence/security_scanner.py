"""Security Scanner (TDD §4, PRD §10). Deterministic vulnerable-pattern detection.

Regex-based checks that need no LLM — a fast, reproducible first pass that complements
the LLM Security agent: injection, command execution, hardcoded secrets (flagged **by
reference only**, never logging the value — PRD §14), weak crypto, insecure
deserialization, and disabled TLS verification.
"""
from __future__ import annotations

import logging
import os
import re

from imperium.api.schemas import Category, Finding

log = logging.getLogger("imperium.intelligence.security_scanner")

_SOURCE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".rb", ".java", ".go", ".php"}
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "tests", "test"}
_MAX_FILE_BYTES = 400_000


# (id, title, compiled pattern, confidence)
_RULES: list[tuple[str, str, re.Pattern, float]] = [
    ("sql_fstring", "Possible SQL injection (f-string interpolation into query)",
     re.compile(r"(execute|executemany|query|raw)\s*\(\s*f['\"].*(SELECT|INSERT|UPDATE|DELETE)", re.IGNORECASE), 0.7),
    ("sql_concat", "Possible SQL injection (string concat/format into query)",
     re.compile(r"(SELECT|INSERT|UPDATE|DELETE)\b.*['\"]\s*(\+|%|\.format)", re.IGNORECASE), 0.65),
    ("shell_true", "Command injection risk (subprocess shell=True)",
     re.compile(r"subprocess\.(run|call|Popen|check_output)\([^)]*shell\s*=\s*True", re.IGNORECASE), 0.75),
    ("os_system", "Command execution via os.system",
     re.compile(r"\bos\.system\s*\("), 0.6),
    ("eval_exec", "Dynamic code execution (eval/exec)",
     re.compile(r"\b(eval|exec)\s*\("), 0.6),
    ("hardcoded_secret", "Hardcoded credential/secret (by reference)",
     re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token|access[_-]?key)\b\s*[:=]\s*['\"][^'\"]{6,}['\"]"), 0.65),
    ("weak_crypto", "Weak hash/cipher (md5/sha1/DES)",
     re.compile(r"(?i)\b(md5|sha1|DES)\b"), 0.5),
    ("pickle_loads", "Insecure deserialization (pickle.loads)",
     re.compile(r"\bpickle\.loads?\s*\("), 0.7),
    ("yaml_load", "Unsafe yaml.load (use safe_load)",
     re.compile(r"\byaml\.load\s*\((?![^)]*Safe)", re.IGNORECASE), 0.6),
    ("tls_verify_off", "TLS verification disabled (verify=False)",
     re.compile(r"verify\s*=\s*False"), 0.7),
]


def _iter_files(repo_path: str):
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() in _SOURCE_EXTS:
                yield os.path.join(root, name)


def scan(repo_path: str) -> list[Finding]:
    """Return deterministic security ``Finding``s across the repository."""
    findings: list[Finding] = []
    for fpath in _iter_files(repo_path):
        try:
            if os.path.getsize(fpath) > _MAX_FILE_BYTES:
                continue
            with open(fpath, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        rel = os.path.relpath(fpath, repo_path)
        for i, line in enumerate(lines, 1):
            for rule_id, title, pattern, confidence in _RULES:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            category=Category.security,
                            title=title,
                            detail=f"Pattern '{rule_id}' matched. Review this line for exploitability.",
                            confidence=confidence,
                            locations=[f"{rel}:{i}"],
                        )
                    )
    log.info("Security scan produced %d findings in %s", len(findings), repo_path)
    return findings
