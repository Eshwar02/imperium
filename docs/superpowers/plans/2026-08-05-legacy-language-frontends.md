# Legacy-Language Frontends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Imperium understand COBOL programs, copybooks, JCL, and DB2/CICS by adding pluggable per-language frontends that feed the existing RKB (Neo4j graph, Postgres modules, Qdrant, rule registry) with no RKB changes.

**Architecture:** A `LanguageFrontend` abstraction in `imperium/intelligence/frontends/`. Each frontend emits the existing `ast_builder.AstNode` shape (module → `function` paragraphs → `call` children) so the current `call_graph.build_call_graph` resolves legacy call edges unchanged, plus extra non-call edges written via `rkb.graph.write_call_graph`. A registry dispatches by language; modern languages keep today's behavior via a `DefaultFrontend`.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, Neo4j driver, Qdrant, pytest. COBOL parsed via a column-aware regex spine (tree-sitter-cobol optional enhancement).

## Global Constraints

- No new required dependencies; tree-sitter-cobol is optional/best-effort only.
- Do NOT modify `imperium/rkb/**` schema or `alembic/**`. Frontends reuse `AstNode` and `write_call_graph(repository_id, nodes, edges)`.
- Every existing test (112) must stay green — `DefaultFrontend` is behavior-preserving.
- Per-file error isolation: one bad file never aborts a run.
- Run tests with `.venv/bin/python -m pytest` from `backend/`.
- New tests under `backend/tests/`, fixtures under `backend/tests/fixtures/legacy/`.

---

### Task 1: Frontend abstraction + registry + DefaultFrontend

**Files:**
- Create: `backend/imperium/intelligence/frontends/__init__.py`
- Create: `backend/imperium/intelligence/frontends/base.py`
- Create: `backend/imperium/intelligence/frontends/default.py`
- Test: `backend/tests/test_frontends_registry.py`

**Interfaces:**
- Produces: `base.LanguageFrontend` (Protocol) with `languages: set[str]`, `preprocess(path, src) -> str`, `structure(path, src) -> AstNode`, `edges(path, root, src) -> list[dict]`, `data_items(path, src) -> list[dict]`.
- Produces: `frontends.get_frontend(language: str) -> LanguageFrontend` — returns the registered frontend or `DefaultFrontend`.
- Produces: `default.DefaultFrontend` wrapping current `parser.parse_file` + `ast_builder.build`.

- [ ] **Step 1: Write failing test**
```python
# backend/tests/test_frontends_registry.py
from imperium.intelligence.frontends import get_frontend
from imperium.intelligence.frontends.default import DefaultFrontend

def test_unknown_language_returns_default():
    fe = get_frontend("python")
    assert isinstance(fe, DefaultFrontend)

def test_default_structure_returns_module_ast():
    fe = get_frontend("python")
    root = fe.structure("x.py", "def foo():\n    bar()\n")
    assert root.kind == "module"
    fns = [c for c in root.children if c.kind == "function"]
    assert any(f.name == "foo" for f in fns)
```

- [ ] **Step 2: Run — expect ImportError/FAIL**
Run: `.venv/bin/python -m pytest tests/test_frontends_registry.py -q`

- [ ] **Step 3: Implement base.py**
```python
# frontends/base.py
from __future__ import annotations
from typing import Protocol
from imperium.intelligence.ast_builder import AstNode

class LanguageFrontend(Protocol):
    languages: set[str]
    def preprocess(self, path: str, src: str) -> str: ...
    def structure(self, path: str, src: str) -> AstNode: ...
    def edges(self, path: str, root: AstNode, src: str) -> list[dict]: ...
    def data_items(self, path: str, src: str) -> list[dict]: ...
```

- [ ] **Step 4: Implement default.py** — wrap existing path.
```python
# frontends/default.py
from __future__ import annotations
from imperium.intelligence.ast_builder import AstNode, build
from imperium.intelligence.parser import parse_file

class DefaultFrontend:
    languages: set[str] = set()  # fallback for everything unregistered
    def preprocess(self, path: str, src: str) -> str:
        return src
    def structure(self, path: str, src: str) -> AstNode:
        pf = parse_file(path)
        return build(pf)  # existing AstNode builder
    def edges(self, path: str, root: AstNode, src: str) -> list[dict]:
        return []
    def data_items(self, path: str, src: str) -> list[dict]:
        return []
```
(Confirm `ast_builder.build(ParsedFile) -> AstNode` signature; adapt call if different.)

- [ ] **Step 5: Implement registry `__init__.py`**
```python
# frontends/__init__.py
from __future__ import annotations
from imperium.intelligence.frontends.base import LanguageFrontend
from imperium.intelligence.frontends.default import DefaultFrontend

_REGISTRY: dict[str, LanguageFrontend] = {}
_DEFAULT = DefaultFrontend()

def register(frontend: LanguageFrontend) -> None:
    for lang in frontend.languages:
        _REGISTRY[lang] = frontend

def get_frontend(language: str) -> LanguageFrontend:
    return _REGISTRY.get(language, _DEFAULT)
```

- [ ] **Step 6: Run tests — expect PASS + full suite green**
Run: `.venv/bin/python -m pytest tests/test_frontends_registry.py -q && .venv/bin/python -m pytest -q`

- [ ] **Step 7: Commit** `git commit -m "feat(frontends): language frontend abstraction + registry + DefaultFrontend"`

---

### Task 2: COBOL preprocessor (format detection + fixed-format strip)

**Files:**
- Create: `backend/imperium/intelligence/frontends/cobol.py`
- Test: `backend/tests/test_cobol_frontend.py`

**Interfaces:**
- Produces: `cobol._detect_format(src) -> "fixed"|"free"`, `cobol._strip_fixed(src) -> str`, `cobol.CobolFrontend.preprocess(path, src) -> str`.

- [ ] **Step 1: Failing test**
```python
# backend/tests/test_cobol_frontend.py
from imperium.intelligence.frontends.cobol import CobolFrontend, _detect_format

FIXED = (
    "000100 IDENTIFICATION DIVISION.\n"
    "000200 PROGRAM-ID. HELLO.\n"
    "000300*THIS IS A COMMENT\n"
    "000400 PROCEDURE DIVISION.\n"
)
def test_detect_fixed_format():
    assert _detect_format(FIXED) == "fixed"

def test_preprocess_strips_seq_and_comments():
    out = CobolFrontend().preprocess("h.cbl", FIXED)
    assert "000100" not in out
    assert "IDENTIFICATION DIVISION." in out
    assert "THIS IS A COMMENT" not in out  # col-7 '*' comment removed
```

- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement** `_detect_format`, `_strip_fixed`, `CobolFrontend.preprocess`:
```python
# frontends/cobol.py (excerpt)
from __future__ import annotations
import re
from imperium.intelligence.ast_builder import AstNode

def _detect_format(src: str) -> str:
    for line in src.splitlines()[:200]:
        if len(line) >= 7 and line[:6].strip().isdigit():
            return "fixed"
        if len(line) >= 7 and line[6:7] in ("*", "/", "-") and line[:6].strip() == "":
            return "fixed"
    return "free"

def _strip_fixed(src: str) -> str:
    out = []
    for line in src.splitlines():
        if len(line) >= 7 and line[6:7] in ("*", "/"):
            continue  # comment line
        body = line[7:72] if len(line) > 7 else ""
        out.append(body.rstrip())
    return "\n".join(out)

class CobolFrontend:
    languages = {"cobol"}
    def preprocess(self, path: str, src: str) -> str:
        return _strip_fixed(src) if _detect_format(src) == "fixed" else src
```

- [ ] **Step 4: Run — PASS**
- [ ] **Step 5: Commit** `git commit -m "feat(cobol): fixed-format detection + preprocessor"`

---

### Task 3: COBOL COPY expansion + copybook index

**Files:**
- Modify: `backend/imperium/intelligence/frontends/cobol.py`
- Test: `backend/tests/test_cobol_frontend.py`

**Interfaces:**
- Produces: `cobol._copy_directives(src) -> list[str]` (copybook member names), `cobol.expand_copies(src, copybook_index) -> tuple[str, list[str]]` returning `(expanded_src, referenced_members)`.

- [ ] **Step 1: Failing test**
```python
from imperium.intelligence.frontends.cobol import expand_copies
def test_expand_copies_inlines_and_records():
    src = " PROCEDURE DIVISION.\n COPY CUSTREC.\n"
    idx = {"CUSTREC": "01 CUST-ID PIC 9(5)."}
    out, refs = expand_copies(src, idx)
    assert "CUST-ID" in out
    assert refs == ["CUSTREC"]
def test_expand_copies_unresolved_still_recorded():
    out, refs = expand_copies(" COPY MISSING.\n", {})
    assert refs == ["MISSING"]
```

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement**
```python
_COPY_RE = re.compile(r"^\s*COPY\s+([A-Z0-9][A-Z0-9-]*)\s*\.?", re.IGNORECASE | re.MULTILINE)

def _copy_directives(src: str) -> list[str]:
    return [m.group(1).upper() for m in _COPY_RE.finditer(src)]

def expand_copies(src: str, copybook_index: dict[str, str]) -> tuple[str, list[str]]:
    refs = _copy_directives(src)
    def repl(m):
        member = m.group(1).upper()
        return copybook_index.get(member, m.group(0))  # unresolved → leave directive
    return _COPY_RE.sub(repl, src), refs
```

- [ ] **Step 4: Run — PASS** ; **Step 5: Commit** `git commit -m "feat(cobol): COPY expansion + copybook refs"`

---

### Task 4: COBOL structure extractor → AstNode (paragraphs + PERFORM/CALL)

**Files:**
- Modify: `backend/imperium/intelligence/frontends/cobol.py`
- Test: `backend/tests/test_cobol_frontend.py`

**Interfaces:**
- Produces: `CobolFrontend.structure(path, src) -> AstNode` — `module` root, `function` children per paragraph, each with `call` children for PERFORM/CALL/GO TO targets. `metadata["cobol_kind"]` set.

- [ ] **Step 1: Failing test**
```python
PROG = (
    "PROGRAM-ID. ORDERS.\n"
    "PROCEDURE DIVISION.\n"
    "MAIN-PARA.\n"
    "    PERFORM VALIDATE-PARA.\n"
    "    CALL 'AUTHSVC'.\n"
    "VALIDATE-PARA.\n"
    "    IF AMT > 0 CONTINUE.\n"
)
def test_structure_paragraphs_and_calls():
    root = CobolFrontend().structure("orders.cbl", PROG)
    assert root.kind == "module"
    paras = {c.name: c for c in root.children if c.kind == "function"}
    assert "MAIN-PARA" in paras and "VALIDATE-PARA" in paras
    calls = [c.name for c in paras["MAIN-PARA"].children if c.kind == "call"]
    assert "VALIDATE-PARA" in calls and "AUTHSVC" in calls
```

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** the regex spine (only PROCEDURE DIVISION paragraphs):
```python
_PARA_RE = re.compile(r"^([A-Z0-9][A-Z0-9-]*)\s*\.\s*$", re.IGNORECASE)
_PERFORM_RE = re.compile(r"\bPERFORM\s+([A-Z0-9][A-Z0-9-]*)", re.IGNORECASE)
_CALL_RE = re.compile(r"\bCALL\s+'([^']+)'", re.IGNORECASE)
_GOTO_RE = re.compile(r"\bGO\s+TO\s+([A-Z0-9][A-Z0-9-]*)", re.IGNORECASE)
_DIV_RE = re.compile(r"\b([A-Z]+)\s+DIVISION\s*\.", re.IGNORECASE)

def _program_id(src: str) -> str:
    m = re.search(r"PROGRAM-ID\.\s+([A-Z0-9-]+)", src, re.IGNORECASE)
    return m.group(1).upper() if m else "PROGRAM"

def _structure(path: str, src: str) -> AstNode:
    lines = src.splitlines()
    root = AstNode(kind="module", name=_program_id(src), metadata={"cobol_kind": "program"})
    in_proc = False
    current: AstNode | None = None
    for i, raw in enumerate(lines):
        line = raw.strip()
        d = _DIV_RE.search(line)
        if d:
            in_proc = d.group(1).upper() == "PROCEDURE"
            current = None
            continue
        if not in_proc or not line:
            continue
        p = _PARA_RE.match(line)
        if p and not any(rx.search(line) for rx in (_PERFORM_RE, _CALL_RE)):
            current = AstNode(kind="function", name=p.group(1).upper(),
                              span=(i + 1, i + 1), metadata={"cobol_kind": "paragraph"})
            root.children.append(current)
            continue
        if current is None:
            continue
        for rx, kind in ((_PERFORM_RE, "perform"), (_GOTO_RE, "goto")):
            for m in rx.finditer(line):
                current.children.append(AstNode(kind="call", name=m.group(1).upper(),
                                                metadata={"cobol_kind": kind}))
        for m in _CALL_RE.finditer(line):
            current.children.append(AstNode(kind="call", name=m.group(1).upper(),
                                            metadata={"cobol_kind": "call"}))
    return root

class CobolFrontend:  # extend
    def structure(self, path: str, src: str) -> AstNode:
        return _structure(path, self.preprocess(path, src))
```

- [ ] **Step 4: Run — PASS** ; **Step 5: Commit** `git commit -m "feat(cobol): paragraph + PERFORM/CALL/GOTO AstNode extractor"`

---

### Task 5: COBOL extra edges (COPIES) + data_items + register frontend

**Files:**
- Modify: `backend/imperium/intelligence/frontends/cobol.py`
- Modify: `backend/imperium/intelligence/frontends/__init__.py` (register CobolFrontend)
- Test: `backend/tests/test_cobol_frontend.py`

**Interfaces:**
- Produces: `CobolFrontend.edges(path, root, src) -> [{"source","target","type"}]` with `COPIES` edges (program→copybook member); `data_items(path, src) -> [{"level","name","pic","is_condition"}]` (88-levels flagged).
- Produces: `get_frontend("cobol")` returns `CobolFrontend`.

- [ ] **Step 1: Failing test**
```python
from imperium.intelligence.frontends import get_frontend
def test_cobol_registered():
    from imperium.intelligence.frontends.cobol import CobolFrontend
    assert isinstance(get_frontend("cobol"), CobolFrontend)
def test_edges_copies():
    fe = CobolFrontend()
    src = "PROGRAM-ID. P.\n COPY CUSTREC.\n"
    root = fe.structure("p.cbl", src)
    edges = fe.edges("p.cbl", root, src)
    assert any(e["type"] == "COPIES" and e["target"] == "CUSTREC" for e in edges)
def test_data_items_88_level():
    items = CobolFrontend().data_items("p.cbl",
        "01 STATUS PIC X.\n 88 IS-ACTIVE VALUE 'A'.\n")
    assert any(d["name"] == "IS-ACTIVE" and d["is_condition"] for d in items)
```

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** `edges`, `data_items`, and `register(CobolFrontend())` in `__init__.py`:
```python
_LEVEL_RE = re.compile(r"^\s*(\d\d)\s+([A-Z0-9-]+)(?:\s+PIC\s+(\S+))?", re.IGNORECASE)

class CobolFrontend:  # extend
    def edges(self, path, root, src):
        prog = root.name
        return [{"source": prog, "target": m, "type": "COPIES"}
                for m in _copy_directives(self.preprocess(path, src))]
    def data_items(self, path, src):
        out = []
        for line in self.preprocess(path, src).splitlines():
            m = _LEVEL_RE.match(line)
            if m:
                out.append({"level": m.group(1), "name": m.group(2).upper(),
                            "pic": (m.group(3) or "").upper(),
                            "is_condition": m.group(1) == "88"})
        return out
```
```python
# frontends/__init__.py append:
from imperium.intelligence.frontends.cobol import CobolFrontend
register(CobolFrontend())
```

- [ ] **Step 4: Run — PASS + full suite** ; **Step 5: Commit** `git commit -m "feat(cobol): COPIES edges + data items + register frontend"`

---

### Task 6: COBOL business-rule candidates (88-level + IF/EVALUATE)

**Files:**
- Modify: `backend/imperium/intelligence/business_rule_extractor.py`
- Test: `backend/tests/test_cobol_rules.py`

**Interfaces:**
- Consumes: `CobolFrontend.data_items`.
- Produces: `_extract_cobol_candidates(source, file_path) -> list[RuleCandidate]`; `_scan_file` dispatches `.cbl/.cob/.cpy` to it.

- [ ] **Step 1: Failing test**
```python
# backend/tests/test_cobol_rules.py
from imperium.intelligence.business_rule_extractor import _extract_cobol_candidates
def test_cobol_88_level_is_rule():
    src = ("01 ACCT-STATUS PIC X.\n"
           " 88 ACCOUNT-CLOSED VALUE 'C'.\n"
           " IF BALANCE < 0 MOVE 'C' TO ACCT-STATUS.\n")
    cands = _extract_cobol_candidates(src, "acct.cbl")
    txts = " ".join(c.text.upper() for c in cands)
    assert "ACCOUNT-CLOSED" in txts
    assert "BALANCE" in txts  # IF condition captured
```

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** (match the existing `RuleCandidate` dataclass fields — read them first):
```python
_COBOL_88_RE = re.compile(r"^\s*88\s+([A-Z0-9-]+)\s+VALUE", re.IGNORECASE | re.MULTILINE)
_COBOL_IF_RE = re.compile(r"\bIF\s+(.+?)(?:\bTHEN\b|$)", re.IGNORECASE)

def _extract_cobol_candidates(source: str, file_path: str) -> list["RuleCandidate"]:
    cands: list[RuleCandidate] = []
    for m in _COBOL_88_RE.finditer(source):
        cands.append(RuleCandidate(
            text=f"Condition name {m.group(1)} defines a business state",
            file_path=file_path, line=source[:m.start()].count("\n") + 1, confidence=0.6))
    for m in _COBOL_IF_RE.finditer(source):
        cond = m.group(1).strip()[:120]
        cands.append(RuleCandidate(
            text=f"Business condition: IF {cond}",
            file_path=file_path, line=source[:m.start()].count("\n") + 1, confidence=0.5))
    return cands
```
Wire in `_scan_file`:
```python
if file_path.lower().endswith((".cbl", ".cob", ".cpy")):
    return _extract_cobol_candidates(source, file_path)
```

- [ ] **Step 4: Run — PASS** ; **Step 5: Commit** `git commit -m "feat(cobol): 88-level + IF business-rule candidates"`

---

### Task 7: Wire frontends into orchestrator KB build

**Files:**
- Modify: `backend/imperium/core/orchestrator.py` (`build_knowledge_base`)
- Test: `backend/tests/test_orchestrator_cobol.py`

**Interfaces:**
- Consumes: `get_frontend`, `write_call_graph`, `call_graph.build_call_graph`.
- Produces: a `_build_legacy_graph(repository_id, parsed, repo_path)` helper that, for files whose language has a non-default frontend, builds AstNodes + edges and writes them to Neo4j; returns counts merged into `results`.

- [ ] **Step 1: Failing test** (mock Neo4j write; assert cobol nodes/edges produced)
```python
# backend/tests/test_orchestrator_cobol.py
from imperium.core.orchestrator import _build_legacy_graph
def test_legacy_graph_from_cobol(tmp_path, monkeypatch):
    f = tmp_path / "orders.cbl"
    f.write_text("PROGRAM-ID. ORDERS.\nPROCEDURE DIVISION.\nMAIN-PARA.\n    PERFORM SUB-PARA.\nSUB-PARA.\n    CONTINUE.\n")
    written = {}
    import imperium.core.orchestrator as orch
    monkeypatch.setattr(orch, "write_call_graph", lambda rid, nodes, edges: written.update(nodes=nodes, edges=edges))
    res = _build_legacy_graph("repo1", [str(f)], str(tmp_path))
    assert res["legacy_nodes"] >= 2
    assert any(e["type"] in ("PERFORMS", "CALLS") for e in written["edges"])
```

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** `_build_legacy_graph` and call it in `build_knowledge_base` after step 2. Build call edges by reusing `call_graph.build_call_graph` on the frontend AstNodes (PERFORM/CALL become CALLS/PERFORMS), then append `frontend.edges(...)`. Import `write_call_graph` at module top for monkeypatchability. Guard each file in try/except.

- [ ] **Step 4: Run — PASS + full suite** ; **Step 5: Commit** `git commit -m "feat: wire legacy frontends into KB build"`

---

### Task 8 (Phase 2): JCL frontend

**Files:**
- Create: `backend/imperium/intelligence/frontends/jcl.py`
- Modify: `backend/imperium/intelligence/frontends/__init__.py` (register)
- Modify: `backend/imperium/intelligence/language_detection.py` (`.jcl/.job` → `jcl`)
- Test: `backend/tests/test_jcl_frontend.py`

**Interfaces:**
- Produces: `JclFrontend.structure` (module=job, children=steps) and `edges` with `RUNS(step→program)`, `USES_DATASET(step→dataset)`.

- [ ] **Step 1: Failing test**
```python
from imperium.intelligence.frontends.jcl import JclFrontend
JCL = ("//PAYJOB JOB (ACCT)\n"
       "//STEP1 EXEC PGM=PAYCALC\n"
       "//IN DD DSN=PROD.PAY.MASTER,DISP=SHR\n")
def test_jcl_runs_and_dataset_edges():
    fe = JclFrontend()
    root = fe.structure("pay.jcl", JCL)
    edges = fe.edges("pay.jcl", root, JCL)
    assert any(e["type"] == "RUNS" and e["target"] == "PAYCALC" for e in edges)
    assert any(e["type"] == "USES_DATASET" and "PROD.PAY.MASTER" in e["target"] for e in edges)
```

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** JCL regexes (`//name JOB`, `EXEC PGM=`, `DD DSN=`), nodes `JclJob/JclStep/Dataset`, register `{"jcl"}`, add extensions to `_EXT_LANG`.
- [ ] **Step 4: Run — PASS + full suite** ; **Step 5: Commit** `git commit -m "feat(jcl): JCL frontend — RUNS/USES_DATASET edges"`

---

### Task 9 (Phase 3): DB2 + CICS edges

**Files:**
- Create: `backend/imperium/intelligence/frontends/mainframe_data.py`
- Modify: `backend/imperium/intelligence/frontends/cobol.py` (`edges` also emit EXEC SQL/CICS)
- Test: `backend/tests/test_db2_cics.py`

**Interfaces:**
- Produces: `extract_sql_edges(program, src) -> list[dict]` with `READS/WRITES(program→Db2Table)`; `extract_cics(program, src) -> list[dict]` with `EXPOSES(program→CicsTransaction)`.

- [ ] **Step 1: Failing test**
```python
from imperium.intelligence.frontends.mainframe_data import extract_sql_edges, extract_cics
def test_exec_sql_read_write():
    src = "EXEC SQL SELECT * FROM CUSTOMER END-EXEC.\nEXEC SQL UPDATE ACCOUNT SET B=0 END-EXEC.\n"
    edges = extract_sql_edges("ORDERS", src)
    assert any(e["type"] == "READS" and e["target"] == "CUSTOMER" for e in edges)
    assert any(e["type"] == "WRITES" and e["target"] == "ACCOUNT" for e in edges)
def test_exec_cics_txn():
    edges = extract_cics("ORDERS", "EXEC CICS RETURN TRANSID('PAY1') END-EXEC.\n")
    assert any(e["type"] == "EXPOSES" and e["target"] == "PAY1" for e in edges)
```

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** SQL verb→table (SELECT/FROM/JOIN→READS; INSERT/UPDATE/DELETE INTO/table→WRITES) and CICS TRANSID/verb parsing; call both from `CobolFrontend.edges`.
- [ ] **Step 4: Run — PASS + full suite** ; **Step 5: Commit** `git commit -m "feat: DB2 READS/WRITES + CICS EXPOSES edges"`

---

### Task 10: Live end-to-end verification on a legacy fixture repo

**Files:**
- Create: `backend/tests/fixtures/legacy/` (orders.cbl, custrec.cpy, pay.jcl, schema.ddl)
- Test: `backend/tests/test_legacy_pipeline_live.py` (marked `@pytest.mark.live`, skipped by default)

**Interfaces:** consumes the full `build_knowledge_base`.

- [ ] **Step 1:** Write a small legacy fixture repo (COBOL program that PERFORMs a paragraph, CALLs a program, COPYs a copybook, has EXEC SQL; a JCL that runs it; a DDL).
- [ ] **Step 2:** Live test (opt-in): run `Orchestrator().build_knowledge_base(rid, fixture)`; assert `graph.repo_graph(rid)` contains program/paragraph/copybook/dataset nodes and PERFORMS/CALLS/COPIES/RUNS/READS edges; assert Postgres has module rows; clean up rows/vectors/nodes after.
- [ ] **Step 3:** Run offline suite green (`.venv/bin/python -m pytest -q`) and the live test manually (`-m live`).
- [ ] **Step 4: Commit** `git commit -m "test: live legacy pipeline verification + fixtures"`

---

## Self-Review

- **Spec coverage:** abstraction (T1) ✓, COBOL preprocess/COPY/structure/rules (T2–T6) ✓, wiring (T7) ✓, JCL (T8) ✓, DB2/CICS (T9) ✓, scale content-hash — *deferred to a follow-up (noted); not blocking P1–P3*. Live testing (T10) ✓.
- **Placeholders:** none — every code step has real code; adapt-if-different notes name the exact symbols to confirm (`ast_builder.build`, `RuleCandidate` fields).
- **Type consistency:** `AstNode(kind,name,span,children,metadata)` used consistently; edge dicts always `{"source","target","type"}`; frontend method names match the Protocol in T1.
- **Gap:** content-hash skip (spec §Scale) is intentionally deferred — call it out at execution; add as Task 11 if desired.
