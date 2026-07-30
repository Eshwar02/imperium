"""AST Builder (TDD §4). Normalizes tree-sitter CSTs + line-scanner output into
a language-agnostic AST used by call graph, dependency, and rule extractors.

Node kinds: module | class | function | method | call | import | constant | variable
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from imperium.intelligence.parser import ParsedFile


@dataclass
class AstNode:
    kind: str
    name: str
    span: tuple[int, int] = (0, 0)
    children: list["AstNode"] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # language-specific extras


# ── tree-sitter traversal ─────────────────────────────────────────────────────

def _ts_node_to_ast(ts_node, source_lines: list[str]) -> AstNode | None:
    """Map a tree-sitter Node to AstNode. Returns None for uninteresting nodes."""
    kind_map = {
        "module": "module",
        "class_definition": "class",
        "function_definition": "function",
        "decorated_definition": "function",
        "method_definition": "method",
        "call": "call",
        "import_statement": "import",
        "import_from_statement": "import",
        "assignment": "variable",
    }
    ts_type = ts_node.type
    ast_kind = kind_map.get(ts_type)
    if ast_kind is None:
        return None

    name = ""
    # Try to find the 'name' child
    for child in ts_node.children:
        if child.type in ("identifier", "dotted_name", "attribute"):
            name = source_lines[child.start_point[0]][child.start_point[1]:child.end_point[1]]
            break

    node = AstNode(
        kind=ast_kind,
        name=name or ts_type,
        span=(ts_node.start_point[0] + 1, ts_node.end_point[0] + 1),
    )

    for child in ts_node.children:
        child_ast = _ts_node_to_ast(child, source_lines)
        if child_ast:
            node.children.append(child_ast)

    return node


# ── regex-based fallback for unsupported languages ────────────────────────────

_PATTERNS: dict[str, list[tuple[re.Pattern, str]]] = {
    "python": [
        (re.compile(r"^class\s+(\w+)"), "class"),
        (re.compile(r"^\s*def\s+(\w+)"), "function"),
        (re.compile(r"^\s*import\s+(.+)"), "import"),
        (re.compile(r"^\s*from\s+\S+\s+import\s+(.+)"), "import"),
    ],
    "javascript": [
        (re.compile(r"^class\s+(\w+)"), "class"),
        (re.compile(r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\())", re.MULTILINE), "function"),
        (re.compile(r"import\s+.+\s+from\s+['\"](.+)['\"]"), "import"),
    ],
    "java": [
        (re.compile(r"\bclass\s+(\w+)"), "class"),
        (re.compile(r"\b(?:public|private|protected|static).*\s+(\w+)\s*\("), "function"),
        (re.compile(r"import\s+([\w.]+)"), "import"),
    ],
    "go": [
        (re.compile(r"^type\s+(\w+)\s+struct"), "class"),
        (re.compile(r"^func\s+(?:\(.*?\)\s+)?(\w+)"), "function"),
        (re.compile(r"^import\s+[\"(](.+)"), "import"),
    ],
}


def _regex_build(parsed: ParsedFile) -> AstNode:
    root = AstNode(kind="module", name=parsed.path, span=(1, len(parsed.lines)))
    patterns = _PATTERNS.get(parsed.language, [])

    for i, line in enumerate(parsed.lines, 1):
        for pat, kind in patterns:
            m = pat.search(line)
            if m:
                name = next((g for g in m.groups() if g), m.group(0)[:40])
                root.children.append(AstNode(kind=kind, name=name.strip(), span=(i, i)))
                break

    return root


# ── public API ────────────────────────────────────────────────────────────────

def build(parsed: ParsedFile) -> AstNode:
    """Build a normalized AST from a ParsedFile.

    Prefers tree-sitter if available; falls back to regex scanner.
    """
    if parsed.tree is not None:
        try:
            root = _ts_node_to_ast(parsed.tree.root_node, parsed.lines)
            if root:
                return root
        except Exception:  # noqa: BLE001
            pass

    return _regex_build(parsed)


def build_all(parsed_files: list[ParsedFile]) -> list[AstNode]:
    """Build ASTs for a list of parsed files."""
    return [build(pf) for pf in parsed_files]
