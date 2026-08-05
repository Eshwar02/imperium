"""Business Rule Extractor (TDD §4, §7). The differentiation core (PRD §10).

Surfaces IMPLICIT rules not in comments/docs (undocumented limits, conditional
exceptions). Low-confidence rules become HITL clarification questions; verified
answers persist to RKB (BusinessRule.verified).

Strategy:
  1. AST heuristics — scan for guards (if x > N), clamps (min/max), magic constants,
     conditional exceptions (raise/throw), null guards, boundary checks.
  2. LLM reading — ask the business_logic LLM to name the implicit rule expressed
     by each heuristic hit (yields natural-language statement + confidence).
  3. Dedup + persist via store.upsert_business_rule (statement hash dedup).
  4. Rules below threshold → HITL question generated and stored.
"""
from __future__ import annotations

import ast
import logging
import os
import re
from dataclasses import dataclass, field

from imperium.api.schemas import Category, Finding

log = logging.getLogger("imperium.intelligence.business_rule_extractor")

_CONFIDENCE_THRESHOLD = 0.70

# AST heuristic patterns — compiled once
_MAGIC_CONST_RE = re.compile(r"\b(\d{2,})\b")  # integers ≥ 10 in expressions


@dataclass
class RuleCandidate:
    """Raw candidate before LLM enrichment."""
    file_path: str
    line: int
    code_snippet: str
    hint: str          # e.g. "magic_constant", "guard", "exception_condition"
    confidence: float = 0.5


@dataclass
class ExtractedRule:
    statement: str
    file_path: str
    line: int
    confidence: float
    hint: str
    hitl_question: str | None = None


# ── AST heuristics ────────────────────────────────────────────────────────────

def _extract_python_candidates(source: str, file_path: str) -> list[RuleCandidate]:
    """Walk Python AST for guards, clamps, magic constants, exception conditions."""
    candidates: list[RuleCandidate] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return candidates

    lines = source.splitlines()

    for node in ast.walk(tree):
        # Guard: if <compare>: raise / return early
        if isinstance(node, ast.If):
            body_raises = any(isinstance(n, (ast.Raise, ast.Return)) for n in ast.walk(node))
            if body_raises and isinstance(node.test, ast.Compare):
                ln = node.lineno - 1
                snippet = lines[ln] if ln < len(lines) else ""
                candidates.append(RuleCandidate(
                    file_path=file_path,
                    line=node.lineno,
                    code_snippet=snippet.strip(),
                    hint="guard",
                    confidence=0.65,
                ))

        # Clamp: call to min() or max() with a literal
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("min", "max"):
                has_literal = any(isinstance(a, ast.Constant) for a in node.args)
                if has_literal:
                    ln = node.lineno - 1
                    snippet = lines[ln] if ln < len(lines) else ""
                    candidates.append(RuleCandidate(
                        file_path=file_path,
                        line=node.lineno,
                        code_snippet=snippet.strip(),
                        hint="clamp",
                        confidence=0.70,
                    ))

        # Magic constant: assignment / comparison to a large integer
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and node.value > 10:
            ln = getattr(node, "lineno", 0) - 1
            snippet = lines[ln] if 0 <= ln < len(lines) else ""
            if re.search(r"\b(limit|max|min|threshold|timeout|retry|size|length|count|rate)\b",
                          snippet, re.IGNORECASE):
                candidates.append(RuleCandidate(
                    file_path=file_path,
                    line=getattr(node, "lineno", 0),
                    code_snippet=snippet.strip(),
                    hint="magic_constant",
                    confidence=0.55,
                ))

    # Deduplicate by line
    seen: set[int] = set()
    unique: list[RuleCandidate] = []
    for c in candidates:
        if c.line not in seen:
            seen.add(c.line)
            unique.append(c)
    return unique


def _extract_generic_candidates(source: str, file_path: str) -> list[RuleCandidate]:
    """Regex-based heuristics for non-Python files."""
    candidates: list[RuleCandidate] = []
    lines = source.splitlines()
    patterns = [
        (re.compile(r"\b(if|when|unless)\b.*\b(throw|raise|return|error|exception)\b", re.IGNORECASE), "guard", 0.60),
        (re.compile(r"\b(Math\.min|Math\.max|clamp|clip)\b", re.IGNORECASE), "clamp", 0.65),
        (re.compile(r"\b(MAX|MIN|LIMIT|THRESHOLD|TIMEOUT|RETRY)\s*[=:]\s*\d+", re.IGNORECASE), "magic_constant", 0.60),
    ]
    for i, line in enumerate(lines, 1):
        for pat, hint, conf in patterns:
            if pat.search(line):
                candidates.append(RuleCandidate(
                    file_path=file_path,
                    line=i,
                    code_snippet=line.strip()[:200],
                    hint=hint,
                    confidence=conf,
                ))
                break
    return candidates


# ── COBOL heuristics ──────────────────────────────────────────────────────────

_COBOL_88_RE = re.compile(r"^\s*88\s+([A-Z0-9-]+)\s+VALUE", re.IGNORECASE | re.MULTILINE)
_COBOL_IF_RE = re.compile(r"\bIF\s+(.+?)(?:\bTHEN\b|$)", re.IGNORECASE | re.MULTILINE)


def _extract_cobol_candidates(source: str, file_path: str) -> list[RuleCandidate]:
    """Regex-scan COBOL for 88-level condition names and IF business guards."""
    candidates: list[RuleCandidate] = []

    for m in _COBOL_88_RE.finditer(source):
        line = source[:m.start()].count("\n") + 1
        name = m.group(1).upper()
        candidates.append(RuleCandidate(
            file_path=file_path,
            line=line,
            code_snippet=f"88-level condition name {name}: {m.group(0).strip()}",
            hint="cobol_condition_name",
            confidence=0.6,
        ))

    for m in _COBOL_IF_RE.finditer(source):
        line = source[:m.start()].count("\n") + 1
        cond = m.group(1).strip()
        if not cond:
            continue
        candidates.append(RuleCandidate(
            file_path=file_path,
            line=line,
            code_snippet=f"IF guard on condition: {cond}",
            hint="cobol_guard",
            confidence=0.5,
        ))

    return candidates


# ── LLM enrichment ────────────────────────────────────────────────────────────

_ENRICH_SYSTEM = (
    "You are a business analyst reading source code. "
    "Given a code snippet and a hint about the pattern, state the implicit business rule "
    "in one natural-language sentence. Also give a confidence score (0.0–1.0) that this is "
    "a real business rule (not just a technical guard). "
    'Respond ONLY with JSON: {"statement": "...", "confidence": 0.0, "question": "..."} '
    "where question is what you would ask a developer to confirm this rule (or null if confident)."
)


def _enrich_candidate(candidate: RuleCandidate) -> ExtractedRule | None:
    """Use LLM to turn a raw candidate into a natural-language rule."""
    from imperium.llm.client import complete

    prompt = (
        f"File: {candidate.file_path} line {candidate.line}\n"
        f"Pattern type: {candidate.hint}\n"
        f"Code snippet: {candidate.code_snippet}\n\n"
        "What is the implicit business rule?"
    )
    try:
        import json
        import re as _re

        text = complete("business_logic", prompt, system=_ENRICH_SYSTEM, temperature=0.1)
        m = _re.search(r"\{.*?\}", text, _re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group())
        statement = data.get("statement", "").strip()
        confidence = float(data.get("confidence", candidate.confidence))
        question = data.get("question") or None
        if not statement:
            return None
        return ExtractedRule(
            statement=statement,
            file_path=candidate.file_path,
            line=candidate.line,
            confidence=confidence,
            hint=candidate.hint,
            hitl_question=question if confidence < _CONFIDENCE_THRESHOLD else None,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("LLM enrichment failed for %s:%d — %s", candidate.file_path, candidate.line, exc)
        # Fall back to a synthetic statement from the snippet
        return ExtractedRule(
            statement=f"Implicit rule at {candidate.file_path}:{candidate.line}: {candidate.code_snippet[:100]}",
            file_path=candidate.file_path,
            line=candidate.line,
            confidence=candidate.confidence,
            hint=candidate.hint,
            hitl_question=f"Can you describe the business rule at {candidate.file_path} line {candidate.line}?",
        )


# ── Public API ────────────────────────────────────────────────────────────────

def _scan_file(file_path: str) -> list[RuleCandidate]:
    """Read a file and run appropriate heuristic scanner."""
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as fh:
            source = fh.read()
    except OSError:
        return []

    if file_path.endswith(".py"):
        return _extract_python_candidates(source, file_path)
    if file_path.lower().endswith((".cbl", ".cob", ".cpy")):
        return _extract_cobol_candidates(source, file_path)
    return _extract_generic_candidates(source, file_path)


def _iter_source_files(repo_path: str) -> list[str]:
    """Walk repo directory, yield source files (skip hidden, vendor, tests)."""
    skip_dirs = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build"}
    skip_exts = {".min.js", ".lock", ".png", ".jpg", ".svg", ".ico", ".woff", ".ttf"}
    result = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for fname in files:
            if any(fname.endswith(e) for e in skip_exts):
                continue
            result.append(os.path.join(root, fname))
    return result


def extract_rules(
    repo_path: str,
    ast_context: object | None = None,
    repository_id: str | None = None,
) -> list[Finding]:
    """Extract business rules from repo_path.

    Returns Finding list (compatible with AnalysisResponse).
    If repository_id is provided, also persists rules to Postgres RKB.
    """
    files = _iter_source_files(repo_path)
    all_candidates: list[RuleCandidate] = []

    for fp in files:
        candidates = _scan_file(fp)
        # Cap per file to avoid flooding the LLM
        all_candidates.extend(candidates[:10])

    log.info("Found %d rule candidates across %d files", len(all_candidates), len(files))

    findings: list[Finding] = []
    rules_for_rkb: list[ExtractedRule] = []

    for candidate in all_candidates[:200]:  # global cap
        rule = _enrich_candidate(candidate)
        if rule is None:
            continue

        findings.append(Finding(
            category=Category.modernization,
            title=f"Business rule @ {os.path.basename(rule.file_path)}:{rule.line}",
            detail=rule.statement,
            confidence=rule.confidence,
            locations=[f"{rule.file_path}:{rule.line}"],
        ))
        rules_for_rkb.append(rule)

    if repository_id and rules_for_rkb:
        _persist_rules(repository_id, rules_for_rkb)

    log.info("Extracted %d business rules from %s", len(findings), repo_path)
    return findings


def _persist_rules(repository_id: str, rules: list[ExtractedRule]) -> None:
    """Persist extracted rules to Postgres + embed in Qdrant."""
    try:
        from imperium.rkb.store import get_session, upsert_business_rule

        session = get_session()
        rule_texts = []
        rule_payloads = []
        try:
            for rule in rules:
                obj = upsert_business_rule(
                    session=session,
                    repository_id=repository_id,
                    statement=rule.statement,
                    locations=[{"file": rule.file_path, "line": rule.line}],
                    confidence=rule.confidence,
                    hitl_question=rule.hitl_question,
                )
                rule_texts.append(rule.statement)
                rule_payloads.append({
                    "repository_id": repository_id,
                    "level": "business_rule",
                    "rule_id": obj.id,
                    "file_path": rule.file_path,
                    "hint": rule.hint,
                })
        finally:
            session.close()

        from imperium.rkb.embeddings import upsert as qdrant_upsert
        if rule_texts:
            qdrant_upsert(rule_texts, rule_payloads)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not persist business rules: %s", exc)
