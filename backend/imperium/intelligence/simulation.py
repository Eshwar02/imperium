"""Transformation Simulation (§1.5).

Dry-run a transformation before it is real:
  old code (expected) → new code (expected output) → diff → confidence score → safety check

Pipeline:
  1. Describe old behavior via LLM (business_logic role)
  2. Generate new code via LLM (implementation role — Codestral)
  3. Build unified diff
  4. LLM reviews diff for behavioral equivalence, outputs confidence 0–1
  5. If confidence < safety_threshold → blocked, escalate to HITL

Results are persisted to simulation_results table and evidence vectors optionally in Qdrant.
"""
from __future__ import annotations

import difflib
import hashlib
import logging

from imperium.llm.client import complete

log = logging.getLogger("imperium.intelligence.simulation")

SAFETY_THRESHOLD = 0.75  # confidence below this → block

_BEHAVIOR_SYSTEM = (
    "You are a code analysis expert. Describe what this code does in terms of business behavior, "
    "inputs, outputs, and side effects. Be precise and concise. Max 200 words."
)

_TRANSFORM_SYSTEM = (
    "You are a world-class code migration expert (Codestral). "
    "Modernize the provided code according to the given instructions while preserving all "
    "business behavior and side effects. Output ONLY the new code, no explanation."
)

_REVIEW_SYSTEM = (
    "You are a code safety reviewer. Given the original code, new code, and their diff, "
    "evaluate whether the transformation is behaviorally equivalent and safe. "
    "Respond ONLY with a JSON object: "
    '{"confidence": <float 0-1>, "safe": <bool>, "concerns": ["<string>", ...]}. '
    "A confidence above 0.75 means safe to proceed."
)


def _build_diff(old_code: str, new_code: str, file_path: str = "file") -> str:
    old_lines = old_code.splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    )
    return "".join(diff)


def _parse_review_json(text: str) -> dict:
    """Extract confidence/safe/concerns from LLM review text."""
    import json
    import re

    # Find JSON block
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:  # noqa: BLE001
            pass
    # Fallback: extract confidence number
    conf_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', text)
    confidence = float(conf_match.group(1)) if conf_match else 0.5
    return {"confidence": confidence, "safe": confidence >= SAFETY_THRESHOLD, "concerns": []}


def describe_behavior(code: str, language: str = "") -> str:
    """Ask LLM to describe current code behavior."""
    prompt = f"Language: {language}\n\nCode:\n```\n{code[:4000]}\n```\n\nDescribe the business behavior:"
    try:
        return complete("business_logic", prompt, system=_BEHAVIOR_SYSTEM)
    except Exception as exc:  # noqa: BLE001
        log.warning("Behavior description failed: %s", exc)
        return f"[behavior description unavailable: {exc}]"


def generate_transformation(old_code: str, instructions: str, language: str = "") -> str:
    """Generate new code from old code + transformation instructions."""
    prompt = (
        f"Language: {language}\n\n"
        f"Original code:\n```\n{old_code[:4000]}\n```\n\n"
        f"Transformation instructions: {instructions}\n\n"
        "New code:"
    )
    try:
        return complete("implementation", prompt, system=_TRANSFORM_SYSTEM)
    except Exception as exc:  # noqa: BLE001
        log.warning("Transformation generation failed: %s", exc)
        return old_code  # fail-safe: return original


def review_transformation(old_code: str, new_code: str, diff: str) -> dict:
    """LLM safety review of the transformation diff."""
    prompt = (
        f"Original code:\n```\n{old_code[:2000]}\n```\n\n"
        f"New code:\n```\n{new_code[:2000]}\n```\n\n"
        f"Diff:\n```diff\n{diff[:3000]}\n```\n\n"
        "Safety review JSON:"
    )
    try:
        text = complete("business_logic", prompt, system=_REVIEW_SYSTEM, temperature=0.0)
        return _parse_review_json(text)
    except Exception as exc:  # noqa: BLE001
        log.warning("Safety review failed: %s", exc)
        return {"confidence": 0.0, "safe": False, "concerns": [str(exc)]}


def run_simulation(
    repository_id: str,
    file_path: str,
    old_code: str,
    instructions: str,
    language: str = "",
    persist: bool = True,
    embed_evidence: bool = True,
) -> dict:
    """Full simulation pipeline for a single file transformation.

    Returns {
        file_path, old_behavior, new_code, predicted_new_behavior,
        diff, confidence_score, safety_passed, blocked, block_reason,
        simulation_id (if persisted)
    }
    """
    log.info("Running simulation for %s in repo %s", file_path, repository_id)

    old_behavior = describe_behavior(old_code, language)
    new_code = generate_transformation(old_code, instructions, language)
    diff = _build_diff(old_code, new_code, file_path)
    review = review_transformation(old_code, new_code, diff)

    confidence = float(review.get("confidence", 0.0))
    safety_passed = confidence >= SAFETY_THRESHOLD
    block_reason = "; ".join(review.get("concerns", [])) if not safety_passed else None

    new_behavior = describe_behavior(new_code, language) if safety_passed else None

    evidence_vector_ids: list = []
    if embed_evidence and safety_passed:
        try:
            from imperium.rkb.embeddings import upsert as qdrant_upsert

            texts = [old_behavior, new_behavior or ""]
            payloads = [
                {"repository_id": repository_id, "level": "simulation", "file_path": file_path, "role": "old"},
                {"repository_id": repository_id, "level": "simulation", "file_path": file_path, "role": "new"},
            ]
            qdrant_upsert(texts, payloads)
            # IDs are deterministic md5-based point ids
            import hashlib as _hlib
            evidence_vector_ids = [
                int(_hlib.md5(t.encode()).hexdigest(), 16) % (2**63)
                for t in texts
            ]
        except Exception as exc:  # noqa: BLE001
            log.warning("Simulation evidence embedding failed: %s", exc)

    simulation_id = None
    if persist:
        try:
            from imperium.rkb.store import get_session, save_simulation

            session = get_session()
            try:
                result = save_simulation(
                    session=session,
                    repository_id=repository_id,
                    file_path=file_path,
                    old_code=old_code,
                    new_code=new_code,
                    diff=diff,
                    confidence_score=confidence,
                    safety_passed=safety_passed,
                    expected_old_behavior=old_behavior,
                    predicted_new_behavior=new_behavior,
                    block_reason=block_reason,
                    evidence_vector_ids=evidence_vector_ids,
                )
                simulation_id = result.id
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not persist simulation: %s", exc)

    if not safety_passed:
        log.warning(
            "Simulation BLOCKED for %s — confidence=%.2f, reason: %s",
            file_path, confidence, block_reason,
        )

    return {
        "simulation_id": simulation_id,
        "file_path": file_path,
        "old_behavior": old_behavior,
        "new_code": new_code,
        "predicted_new_behavior": new_behavior,
        "diff": diff,
        "confidence_score": confidence,
        "safety_passed": safety_passed,
        "blocked": not safety_passed,
        "block_reason": block_reason,
        "evidence_vector_ids": evidence_vector_ids,
    }


def run_batch_simulation(
    repository_id: str,
    files: list[dict],
    instructions: str,
    language: str = "",
) -> list[dict]:
    """Simulate transformations for multiple files.

    files: list of {file_path, code}
    Returns list of simulation results.
    """
    results = []
    for f in files:
        result = run_simulation(
            repository_id=repository_id,
            file_path=f["file_path"],
            old_code=f["code"],
            instructions=instructions,
            language=language,
        )
        results.append(result)
    return results
