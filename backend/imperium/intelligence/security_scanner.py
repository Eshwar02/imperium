"""Security Scanner (TDD §4, PRD §10). Deterministic vulnerable-pattern detection.

<<<<<<< HEAD
Detects:
  - Injection vulnerabilities (SQL injection, command injection, path traversal).
  - Authentication bypass patterns (hardcoded credentials, weak auth checks).
  - Secrets in code — flagged BY REFERENCE only (value is never logged per PRD §14).
  - Insecure dependency detection (known vulnerable package versions via local heuristics;
    no external CVE API call to avoid network dependency in CI).

Strategy:
  1. Regex-based pattern scan per file (language-aware where possible).
  2. Dependency file scan (requirements.txt, package.json, pom.xml) for known-bad ranges.
  3. Returns Finding list with category=security and confidence scores.
"""
from __future__ import annotations

import ast
import logging
import os
import re
from dataclasses import dataclass, field
=======
Regex-based checks that need no LLM — a fast, reproducible first pass that complements
the LLM Security agent: injection, command execution, hardcoded secrets (flagged **by
reference only**, never logging the value — PRD §14), weak crypto, insecure
deserialization, and disabled TLS verification.
"""
from __future__ import annotations

import logging
import os
import re
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11

from imperium.api.schemas import Category, Finding

log = logging.getLogger("imperium.intelligence.security_scanner")

<<<<<<< HEAD
# ── Pattern registry ──────────────────────────────────────────────────────────

@dataclass
class _Pattern:
    name: str
    pattern: re.Pattern
    confidence: float
    detail_template: str


_PATTERNS: list[_Pattern] = [
    # SQL injection: string formatting into SQL keywords
    _Pattern(
        name="sql_injection",
        pattern=re.compile(
            r"""(?:execute|cursor\.execute|query|raw)\s*\(\s*(?:f['"]|['"].*%|.*format\()""",
            re.IGNORECASE,
        ),
        confidence=0.80,
        detail_template="Possible SQL injection: string interpolation in DB query at {location}",
    ),
    # Command injection: subprocess/os.system with user-controlled input
    _Pattern(
        name="cmd_injection",
        pattern=re.compile(
            r"""(?:os\.system|subprocess\.(?:call|run|Popen|check_output))\s*\(.*(?:f['"]|\+|format)""",
            re.IGNORECASE,
        ),
        confidence=0.75,
        detail_template="Possible command injection: dynamic shell command at {location}",
    ),
    # Path traversal
    _Pattern(
        name="path_traversal",
        pattern=re.compile(
            r"""open\s*\(\s*(?:f['"]|.*\+|.*format).*\)|os\.path\.join\s*\(.*request""",
            re.IGNORECASE,
        ),
        confidence=0.65,
        detail_template="Possible path traversal: user-controlled file path at {location}",
    ),
    # Hardcoded secrets — flag by reference only (no value logged)
    _Pattern(
        name="hardcoded_secret",
        pattern=re.compile(
            r"""(?:password|passwd|secret|api_key|token|auth_token|private_key)\s*=\s*['"][^'"]{6,}['"]""",
            re.IGNORECASE,
        ),
        confidence=0.85,
        detail_template="Possible hardcoded credential at {location} (value not logged)",
    ),
    # Weak authentication — always-True auth checks
    _Pattern(
        name="weak_auth",
        pattern=re.compile(
            r"""if\s+(?:True|1|not\s+False)\s*:\s*(?:#.*)?$|authenticate\s*\(.*\)\s*==\s*(?:True|None)""",
            re.IGNORECASE,
        ),
        confidence=0.70,
        detail_template="Possible weak auth check (always-true condition) at {location}",
    ),
    # eval() / exec() with non-literal
    _Pattern(
        name="unsafe_eval",
        pattern=re.compile(
            r"""\b(?:eval|exec)\s*\(\s*(?!['"\d\[\{])""",
            re.IGNORECASE,
        ),
        confidence=0.90,
        detail_template="Unsafe eval/exec with non-literal input at {location}",
    ),
    # Insecure deserialization
    _Pattern(
        name="insecure_deserialize",
        pattern=re.compile(
            r"""\bpickle\.(?:load|loads|Unpickler)\b|\byaml\.(?:load)\s*\((?!.*Loader)""",
            re.IGNORECASE,
        ),
        confidence=0.80,
        detail_template="Insecure deserialization (pickle/unsafe yaml.load) at {location}",
    ),
    # Debug/dev endpoints left in
    _Pattern(
        name="debug_endpoint",
        pattern=re.compile(
            r"""DEBUG\s*=\s*True|app\.run\s*\(.*debug\s*=\s*True""",
            re.IGNORECASE,
        ),
        confidence=0.75,
        detail_template="Debug mode enabled in production code at {location}",
    ),
]

_SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build"}
_SKIP_EXTS = {".pyc", ".min.js", ".lock", ".png", ".jpg", ".svg", ".ico", ".woff", ".ttf"}

# ── Dependency vulnerability heuristics ──────────────────────────────────────

# Known-bad package version patterns (simplified; not a full CVE DB)
# Format: {package_name: (bad_version_re, description, confidence)}
_KNOWN_BAD_DEPS: dict[str, tuple[re.Pattern, str, float]] = {
    "flask": (re.compile(r"^0\.[0-9]\."), "Flask <1.0 has known security issues", 0.70),
    "django": (re.compile(r"^[12]\.[0-1]\."), "Django <2.2 reached EOL; security updates stopped", 0.80),
    "requests": (re.compile(r"^2\.[0-9]\."), "requests <2.20 has CVE-2018-18074 (redirect credential leak)", 0.60),
    "pyyaml": (re.compile(r"^[0-4]\."), "PyYAML <5.1 has arbitrary code execution via yaml.load()", 0.85),
    "cryptography": (re.compile(r"^[0-2]\."), "cryptography <3.0 has multiple CVEs", 0.75),
    "pillow": (re.compile(r"^[0-6]\."), "Pillow <7.0 has multiple CVEs (buffer overflow, RCE)", 0.80),
    "urllib3": (re.compile(r"^1\.[0-9]\."), "urllib3 <1.26 has CVE-2021-33503 (ReDoS)", 0.65),
    "werkzeug": (re.compile(r"^0\.[0-9]\."), "Werkzeug <1.0 has path traversal vulnerability", 0.70),
}


def _scan_requirements_txt(file_path: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Parse package==version or package>=version etc.
                m = re.match(r"^([a-zA-Z0-9_.-]+)\s*[=><~!]+\s*([0-9][^\s;,]+)?", line)
                if not m:
                    continue
                pkg = m.group(1).lower().replace("-", "_").replace(".", "_")
                ver = m.group(2) or ""
                for dep_name, (bad_re, desc, conf) in _KNOWN_BAD_DEPS.items():
                    if pkg.startswith(dep_name.replace("-", "_")) and bad_re.match(ver):
                        findings.append(Finding(
                            category=Category.security,
                            title=f"Vulnerable dependency: {m.group(1)}=={ver}",
                            detail=desc,
                            confidence=conf,
                            locations=[file_path],
                        ))
    except OSError as exc:
        log.debug("Cannot read %s: %s", file_path, exc)
    return findings


def _scan_package_json(file_path: str) -> list[Finding]:
    import json

    findings: list[Finding] = []
    try:
        with open(file_path, encoding="utf-8") as fh:
            data = json.load(fh)
        deps = {}
        deps.update(data.get("dependencies", {}))
        deps.update(data.get("devDependencies", {}))
        for pkg, ver_spec in deps.items():
            ver = ver_spec.lstrip("^~>=<").split(" ")[0]
            pkg_norm = pkg.lower().replace("-", "_")
            for dep_name, (bad_re, desc, conf) in _KNOWN_BAD_DEPS.items():
                if pkg_norm == dep_name.replace("-", "_") and bad_re.match(ver):
                    findings.append(Finding(
                        category=Category.security,
                        title=f"Vulnerable dependency: {pkg}@{ver}",
                        detail=desc,
                        confidence=conf,
                        locations=[file_path],
                    ))
    except Exception as exc:  # noqa: BLE001
        log.debug("Cannot parse %s: %s", file_path, exc)
    return findings


def _scan_file_patterns(file_path: str) -> list[Finding]:
    """Regex pattern scan against a single file."""
    findings: list[Finding] = []
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
    except OSError:
        return findings

    for i, line in enumerate(lines, 1):
        for pat in _PATTERNS:
            if pat.pattern.search(line):
                location = f"{file_path}:{i}"
                findings.append(Finding(
                    category=Category.security,
                    title=f"Security: {pat.name.replace('_', ' ').title()}",
                    detail=pat.detail_template.format(location=location),
                    confidence=pat.confidence,
                    locations=[location],
                ))
                break  # one finding per line per file

    return findings


def scan(repo_path: str) -> list[Finding]:
    """Scan repo_path for security vulnerabilities. Returns list of Findings."""
    all_findings: list[Finding] = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            if any(fname.endswith(e) for e in _SKIP_EXTS):
                continue

            fp = os.path.join(root, fname)

            # Dependency files
            if fname == "requirements.txt" or fname.startswith("requirements"):
                all_findings.extend(_scan_requirements_txt(fp))
                continue
            if fname == "package.json":
                all_findings.extend(_scan_package_json(fp))
                continue

            # Source files — pattern scan
            ext = os.path.splitext(fname)[1].lower()
            if ext in (".py", ".js", ".ts", ".java", ".go", ".rb", ".php", ".sh"):
                all_findings.extend(_scan_file_patterns(fp))

    # Deduplicate by (title, location)
    seen: set[tuple] = set()
    unique: list[Finding] = []
    for f in all_findings:
        key = (f.title, tuple(f.locations))
        if key not in seen:
            seen.add(key)
            unique.append(f)

    log.info("Security scanner: %d findings in %s", len(unique), repo_path)
    return unique
=======
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
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
