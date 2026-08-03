"""API Mapper (TDD §4). Catalogues exposed + consumed API contracts (PRD Step 2).

<<<<<<< HEAD
Detects routes (Flask/FastAPI decorators, OpenAPI), REST/GraphQL calls, SDK usage;
records method, path, request/response shape, call sites.

Strategy:
  1. FastAPI/Flask decorator scan — AST walk for @router.get/post/put/delete/patch,
     @app.route, @bp.route patterns.
  2. HTTP client call scan — regex for requests.get/post, httpx.get/post, fetch(),
     axios.get/post, etc.
  3. OpenAPI spec detection — load openapi.json/swagger.yaml if present.
  4. GraphQL schema detection — *.graphql / *.gql files.
"""
from __future__ import annotations

import ast
import json
import logging
import os
import re
from dataclasses import dataclass, field

log = logging.getLogger("imperium.intelligence.api_mapper")

# Regex for HTTP client calls (non-AST languages / JS)
_HTTP_CLIENT_RE = re.compile(
    r"""(?x)
    (?:requests|httpx|urllib\.request|aiohttp\.ClientSession)
    \s*\.\s*(get|post|put|delete|patch|head|options)
    \s*\(\s*['"](.*?)['"]
    |
    (?:fetch|axios\.(?:get|post|put|delete|patch))\s*\(\s*['"](.*?)['"]
    """,
    re.IGNORECASE,
)

_OPENAPI_NAMES = frozenset({"openapi.json", "openapi.yaml", "swagger.json", "swagger.yaml"})
_GRAPHQL_EXTS = frozenset({".graphql", ".gql"})

_SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build"}


@dataclass
class ApiEndpoint:
    kind: str           # "exposed" | "consumed"
    method: str
    path: str
    call_sites: list[str] = field(default_factory=list)
    contract: dict = field(default_factory=dict)


def _ast_scan_python(source: str, file_path: str) -> list[ApiEndpoint]:
    """Walk Python AST for FastAPI/Flask route decorators."""
    endpoints: list[ApiEndpoint] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return endpoints

    lines = source.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            # Match: @router.get("/path"), @app.route("/path"), @bp.route("/path")
            if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute):
                method_name = deco.func.attr.lower()
                if method_name in ("get", "post", "put", "delete", "patch", "head", "options", "route"):
                    path_arg = ""
                    if deco.args and isinstance(deco.args[0], ast.Constant):
                        path_arg = str(deco.args[0].value)
                    methods = [method_name] if method_name != "route" else ["GET"]
                    # Flask @route may have methods kww
                    for kw in deco.keywords:
                        if kw.arg == "methods" and isinstance(kw.value, ast.List):
                            methods = [
                                e.value.upper() for e in kw.value.elts
                                if isinstance(e, ast.Constant)
                            ]
                    for m in methods:
                        endpoints.append(ApiEndpoint(
                            kind="exposed",
                            method=m.upper(),
                            path=path_arg,
                            call_sites=[f"{file_path}:{node.lineno}"],
                        ))

    # Scan for HTTP client calls
    for i, line in enumerate(lines, 1):
        m = _HTTP_CLIENT_RE.search(line)
        if m:
            http_method = (m.group(1) or m.group(0).split("(")[0].split(".")[-1]).upper()
            url = m.group(2) or m.group(3) or ""
            endpoints.append(ApiEndpoint(
                kind="consumed",
                method=http_method,
                path=url,
                call_sites=[f"{file_path}:{i}"],
            ))

    return endpoints


def _regex_scan(source: str, file_path: str) -> list[ApiEndpoint]:
    """Generic regex scan for HTTP calls in non-Python files."""
    endpoints: list[ApiEndpoint] = []
    for i, line in enumerate(source.splitlines(), 1):
        m = _HTTP_CLIENT_RE.search(line)
        if m:
            method = (m.group(1) or "GET").upper()
            url = m.group(2) or m.group(3) or ""
            endpoints.append(ApiEndpoint(
                kind="consumed",
                method=method,
                path=url,
                call_sites=[f"{file_path}:{i}"],
            ))
    return endpoints


def _load_openapi_spec(spec_path: str) -> list[ApiEndpoint]:
    """Parse an OpenAPI/Swagger spec and return exposed endpoints."""
    endpoints: list[ApiEndpoint] = []
    try:
        if spec_path.endswith((".yaml", ".yml")):
            try:
                import yaml  # optional

                with open(spec_path, encoding="utf-8") as fh:
                    spec = yaml.safe_load(fh)
            except ImportError:
                return endpoints
        else:
            with open(spec_path, encoding="utf-8") as fh:
                spec = json.load(fh)

        for path, path_item in (spec.get("paths") or {}).items():
            for method, op in path_item.items():
                if method.lower() in ("get", "post", "put", "delete", "patch", "head", "options"):
                    endpoints.append(ApiEndpoint(
                        kind="exposed",
                        method=method.upper(),
                        path=path,
                        call_sites=[spec_path],
                        contract={
                            "summary": op.get("summary", ""),
                            "operationId": op.get("operationId", ""),
                        },
                    ))
    except Exception as exc:  # noqa: BLE001
        log.warning("OpenAPI spec parse failed for %s: %s", spec_path, exc)
    return endpoints


def _scan_graphql(gql_path: str) -> list[ApiEndpoint]:
    """Detect GraphQL schema files as a single 'exposed' GraphQL endpoint."""
    return [ApiEndpoint(
        kind="exposed",
        method="GRAPHQL",
        path="/graphql",
        call_sites=[gql_path],
        contract={"schema_file": gql_path},
    )]


def map_apis(repo_path: str) -> list[dict]:
    """Return [{kind, method, path, call_sites, contract}] for all detected API endpoints."""
    all_endpoints: list[ApiEndpoint] = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            fp = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()

            # OpenAPI / Swagger specs
            if fname.lower() in _OPENAPI_NAMES:
                all_endpoints.extend(_load_openapi_spec(fp))
                continue

            # GraphQL schemas
            if ext in _GRAPHQL_EXTS:
                all_endpoints.extend(_scan_graphql(fp))
                continue

            # Python — AST scan
            if ext == ".py":
                try:
                    with open(fp, encoding="utf-8", errors="ignore") as fh:
                        source = fh.read()
                    all_endpoints.extend(_ast_scan_python(source, fp))
                except OSError:
                    pass
                continue

            # JS/TS/other — regex scan
            if ext in (".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb"):
                try:
                    with open(fp, encoding="utf-8", errors="ignore") as fh:
                        source = fh.read()
                    all_endpoints.extend(_regex_scan(source, fp))
                except OSError:
                    pass

    # Deduplicate by (kind, method, path)
    seen: set[tuple] = set()
    unique: list[ApiEndpoint] = []
    for ep in all_endpoints:
        key = (ep.kind, ep.method, ep.path)
        if key not in seen:
            seen.add(key)
            unique.append(ep)
        else:
            # Merge call_sites
            for u in unique:
                if (u.kind, u.method, u.path) == key:
                    u.call_sites.extend(ep.call_sites)
                    break

    log.info("API mapper: %d endpoints detected in %s", len(unique), repo_path)

    return [
        {
            "kind": ep.kind,
            "method": ep.method,
            "path": ep.path,
            "call_sites": ep.call_sites,
            "contract": ep.contract,
        }
        for ep in unique
    ]
=======
Detects, per source file:
  - **Exposed** HTTP routes — FastAPI/Flask/Django-style decorators
    (``@app.get("/x")``, ``@router.post(...)``, ``@app.route("/x", methods=[...])``).
  - **Consumed** HTTP calls — ``requests``/``httpx``/``urllib`` and ``fetch``/``axios``
    with an inferable method + URL/path.

Pragmatic regex detection (Python/JS-first) that degrades gracefully — an enterprise
codebase is scanned file-by-file so a weird file never fails the whole map. Feeds the
**API graph** layer (EXPOSES / CONSUMES edges) in Neo4j.
"""
from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("imperium.intelligence.api_mapper")

_SOURCE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java"}
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".mypy_cache"}
_MAX_FILE_BYTES = 400_000

# @app.get("/path")  /  @router.post('/path')  /  @blueprint.route("/path")
_DECORATOR_ROUTE = re.compile(
    r"@\w+\.(get|post|put|patch|delete|route)\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
# methods=["GET","POST"] on Flask/Django @route
_METHODS_KW = re.compile(r"methods\s*=\s*\[([^\]]*)\]", re.IGNORECASE)

# requests.get("http://..") / httpx.post('/api/x') / client.delete(url)
_CONSUMED_CALL = re.compile(
    r"(?:requests|httpx|client|session|urllib\.request)\.(get|post|put|patch|delete)\(\s*(?:f?['\"]([^'\"]*)['\"])?",
    re.IGNORECASE,
)
# JS: fetch("/api/x", {method:"POST"}) / axios.get("/x")
_FETCH_CALL = re.compile(r"\bfetch\(\s*[`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)
_AXIOS_CALL = re.compile(r"\baxios\.(get|post|put|patch|delete)\(\s*[`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)


def _iter_files(repo_path: str):
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() in _SOURCE_EXTS:
                yield os.path.join(root, name)


def _read(path: str) -> list[str] | None:
    try:
        if os.path.getsize(path) > _MAX_FILE_BYTES:
            return None
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return None


def map_apis(repo_path: str) -> list[dict]:
    """Return API records: [{kind: exposed|consumed, method, path, call_sites}].

    ``call_sites`` are ``file:line`` strings; identical (kind, method, path) records are
    merged across files with their sites accumulated.
    """
    records: dict[tuple[str, str, str], dict] = {}

    def _add(kind: str, method: str, path: str, site: str) -> None:
        key = (kind, method.upper(), path)
        rec = records.setdefault(
            key, {"kind": kind, "method": method.upper(), "path": path, "call_sites": []}
        )
        if site not in rec["call_sites"]:
            rec["call_sites"].append(site)

    for fpath in _iter_files(repo_path):
        lines = _read(fpath)
        if lines is None:
            continue
        rel = os.path.relpath(fpath, repo_path)
        for i, line in enumerate(lines, 1):
            site = f"{rel}:{i}"

            m = _DECORATOR_ROUTE.search(line)
            if m:
                verb, path = m.group(1), m.group(2)
                if verb.lower() == "route":
                    methods = _METHODS_KW.search(line)
                    verbs = (
                        [v.strip(" '\"").upper() for v in methods.group(1).split(",") if v.strip()]
                        if methods
                        else ["GET"]
                    )
                    for v in verbs:
                        _add("exposed", v, path, site)
                else:
                    _add("exposed", verb, path, site)

            for cm in _CONSUMED_CALL.finditer(line):
                _add("consumed", cm.group(1), cm.group(2) or "<dynamic>", site)
            for fm in _FETCH_CALL.finditer(line):
                _add("consumed", "GET", fm.group(1), site)
            for am in _AXIOS_CALL.finditer(line):
                _add("consumed", am.group(1), am.group(2), site)

    result = list(records.values())
    log.info("Mapped %d API records from %s", len(result), repo_path)
    return result
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
