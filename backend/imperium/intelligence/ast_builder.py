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


# Call-site detection: `name(` or `obj.name(` — captures the (final) callee name.
# Excludes control-flow keywords that look like calls (if/for/while/return/…).
_CALL_RE = re.compile(r"(?:\b(\w+)\s*\.\s*)?\b(\w+)\s*\(")
_CALL_KEYWORDS = frozenset({
    "if", "for", "while", "return", "with", "elif", "except", "print",
    "def", "class", "and", "or", "not", "in", "is", "assert", "raise",
    "yield", "await", "lambda", "super", "switch", "catch", "function",
})


def _collect_call_children(body_lines: list[tuple[int, str]]) -> list[AstNode]:
    """Extract call-site AstNodes ('call' kind) from a block of (lineno, text) lines."""
    calls: list[AstNode] = []
    seen: set[str] = set()
    for lineno, text in body_lines:
        for m in _CALL_RE.finditer(text):
            attr_owner, callee = m.group(1), m.group(2)
            # Prefer the attribute/method name; both plain foo() and obj.foo().
            name = callee
            if not name or name in _CALL_KEYWORDS:
                continue
            key = f"{name}:{lineno}"
            if key in seen:
                continue
            seen.add(key)
            calls.append(AstNode(kind="call", name=name, span=(lineno, lineno)))
    return calls


def _python_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _regex_build_python(parsed: ParsedFile) -> AstNode:
    """Indentation-aware Python fallback: proper def/class spans + nested call sites."""
    root = AstNode(kind="module", name=parsed.path, span=(1, max(len(parsed.lines), 1)))
    lines = parsed.lines
    class_re = _PATTERNS["python"][0][0]
    def_re = _PATTERNS["python"][1][0]
    import_re1 = _PATTERNS["python"][2][0]
    import_re2 = _PATTERNS["python"][3][0]

    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        lineno = i + 1
        stripped = line.strip()

        # Imports (top-level only, cheap)
        if import_re2.search(line) or import_re1.search(line):
            m = import_re2.search(line) or import_re1.search(line)
            root.children.append(AstNode(kind="import", name=m.group(1).strip(), span=(lineno, lineno)))
            i += 1
            continue

        m_class = class_re.search(line)
        m_def = def_re.search(line)
        if m_class or m_def:
            kind = "class" if m_class else "function"
            name = (m_class or m_def).group(1).strip()
            header_indent = _python_indent(line)
            # Find end of block: next line at <= header_indent that is non-blank.
            j = i + 1
            while j < n:
                nxt = lines[j]
                if nxt.strip() and _python_indent(nxt) <= header_indent:
                    break
                j += 1
            span = (lineno, j)  # 1-based inclusive end
            node = AstNode(kind=kind, name=name, span=span)
            body = [(k + 1, lines[k]) for k in range(i + 1, j)]
            # Methods = defs nested inside a class; recurse one level for classes.
            if kind == "class":
                node.children.extend(_regex_scan_block(body, "python", header_indent))
            else:
                node.children.extend(_collect_call_children(body))
            root.children.append(node)
            i = j
            continue
        i += 1

    return root


def _regex_scan_block(body: list[tuple[int, str]], language: str, parent_indent: int) -> list[AstNode]:
    """Scan a class body for methods (def) and their call sites."""
    def_re = _PATTERNS["python"][1][0]
    children: list[AstNode] = []
    n = len(body)
    i = 0
    while i < n:
        lineno, line = body[i]
        m_def = def_re.search(line)
        if m_def:
            name = m_def.group(1).strip()
            header_indent = _python_indent(line)
            j = i + 1
            while j < n:
                _, nxt = body[j]
                if nxt.strip() and _python_indent(nxt) <= header_indent:
                    break
                j += 1
            method = AstNode(kind="method", name=name, span=(lineno, body[j - 1][0] if j <= n else lineno))
            method.children.extend(_collect_call_children(body[i + 1:j]))
            children.append(method)
            i = j
            continue
        i += 1
    return children


def _regex_build(parsed: ParsedFile) -> AstNode:
    if parsed.language == "python":
        return _regex_build_python(parsed)

    root = AstNode(kind="module", name=parsed.path, span=(1, len(parsed.lines)))
    patterns = _PATTERNS.get(parsed.language, [])

    current_def: AstNode | None = None
    for i, line in enumerate(parsed.lines, 1):
        matched = False
        for pat, kind in patterns:
            m = pat.search(line)
            if m:
                name = next((g for g in m.groups() if g), m.group(0)[:40])
                node = AstNode(kind=kind, name=name.strip(), span=(i, i))
                root.children.append(node)
                if kind in ("function", "class"):
                    current_def = node
                matched = True
                break
        if not matched and current_def is not None:
            # Attach call sites found in the body to the most recent definition.
            current_def.children.extend(_collect_call_children([(i, line)]))
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
