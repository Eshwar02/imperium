"""Language Detection (TDD §4). Foundation: extension-based first pass.

TODO(team): weight by manifest files (requirements.txt, package.json, pom.xml),
handle COBOL (.cbl/.cob/.cpy) per TDD §12, return ranked list with LOC.
"""
from __future__ import annotations

import os
from collections import Counter

_EXT_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".cbl": "cobol",
    ".cob": "cobol",
    ".cpy": "cobol",
}


def detect(repo_path: str) -> list[str]:
    counts: Counter[str] = Counter()
    for root, _dirs, files in os.walk(repo_path):
        if "/.git" in root:
            continue
        for f in files:
            lang = _EXT_LANG.get(os.path.splitext(f)[1].lower())
            if lang:
                counts[lang] += 1
    return [lang for lang, _ in counts.most_common()]
