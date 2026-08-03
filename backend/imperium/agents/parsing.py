"""Shared parsing for agent LLM output.

Analysis agents (research, security, compatibility, …) all ask the model for a JSON
array of findings and must parse it defensively — models wrap JSON in prose, emit
trailing commentary, or occasionally malform an entry. This centralizes that logic so
every agent parses identically.
"""
from __future__ import annotations

import json
import logging
import re

from imperium.api.schemas import Category, Finding

log = logging.getLogger("imperium.agents.parsing")


def parse_findings(
    text: str,
    default_category: str = "modernization",
    default_confidence: float = 0.7,
    limit: int = 20,
) -> list[Finding]:
    """Extract a JSON findings array from an LLM message into ``Finding`` objects.

    Tolerant of surrounding prose and malformed entries (skipped individually).
    """
    match = re.search(r"\[.*\]", text or "", re.DOTALL)
    if not match:
        return []
    try:
        raw = json.loads(match.group())
    except json.JSONDecodeError:
        log.debug("findings JSON did not parse")
        return []
    if not isinstance(raw, list):
        return []

    findings: list[Finding] = []
    for item in raw[:limit]:
        if not isinstance(item, dict):
            continue
        try:
            findings.append(
                Finding(
                    category=Category(item.get("category", default_category)),
                    title=item.get("title", "Finding"),
                    detail=item.get("detail", ""),
                    confidence=float(item.get("confidence", default_confidence)),
                    locations=item.get("locations", []) or [],
                )
            )
        except (ValueError, TypeError):
            continue
    return findings
