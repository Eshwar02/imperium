# Legacy-Language Frontends (COBOL + JCL + DB2/CICS) — Design

**Date:** 2026-08-05
**Status:** Approved, ready for implementation plan
**Author:** Imperium build session

## Goal

Make Imperium's Repo Intelligence Engine actually *understand* huge legacy mainframe
codebases — COBOL programs, their copybooks, the JCL that runs them, and the DB2/CICS
resources they touch — so the same downstream machinery (Neo4j graph, blast radius,
Postgres modules, Qdrant semantic memory, business-rule registry, priority, gates)
works on legacy systems with **no RKB changes**.

## Problem (current state)

- `language_detection` already tags COBOL (`.cbl/.cob/.cpy`) — detection is fine.
- `parser.py` maps **only modern languages** to tree-sitter; everything else falls to a
  generic line-scanner, then `ast_builder`'s **Python-indentation** fallback.
- COBOL is **columnar, period-terminated, division/section/paragraph-structured**, with
  flow via `PERFORM/CALL/GO TO/COPY` — none of which the current fallbacks recognize.
  Result: COBOL is detected but yields a garbage structure and **zero real call edges**.
- The real legacy unit of analysis is not a single `.cbl` — it is
  `JCL job → step → program → copybook → DB2 table / VSAM dataset`. That cross-artifact
  graph is where legacy impact-analysis lives, and it is exactly Imperium's
  Neo4j/blast-radius strength.

## Architecture: pluggable language frontends

New package `imperium/intelligence/frontends/`. A **frontend** owns everything
language-specific; the rest of the pipeline stays generic.

```python
class LanguageFrontend(Protocol):
    languages: set[str]                                  # e.g. {"cobol"}
    def preprocess(self, path: str, src: str) -> str: ...        # normalize source
    def structure(self, path: str, src: str) -> AstNode: ...     # reuse existing AstNode
    def edges(self, path: str, root: AstNode, src: str) -> list[dict]: ...  # extra rels
    def data_items(self, path: str, src: str) -> list[dict]: ... # for rule extractor
```

- **Reuse `ast_builder.AstNode`** (`kind, name, span, children, metadata`) unchanged.
- **Registry** in `frontends/__init__.py`: `get_frontend(language) -> LanguageFrontend`.
  Modern languages are served by a `DefaultFrontend` that wraps today's
  tree-sitter/regex + `ast_builder` path (behavior-preserving; existing tests stay green).
- **Key integration trick:** a frontend emits `AstNode` trees in the *same shape the
  Python path already produces* — a `module` root whose children are `function` nodes
  (COBOL paragraphs/sections) that contain `call` children (PERFORM/CALL targets). That
  means the **existing `call_graph.build_call_graph` resolves COBOL call edges with no
  change** — paragraphs become graph nodes, PERFORM/CALL become edges.
- Frontends may additionally return **non-call edges** (COPIES, READS/WRITES, RUNS,
  USES_DATASET, STARTS/EXPOSES) via `edges()`, which the orchestrator writes to Neo4j
  through the existing `rkb.graph.write_call_graph(repository_id, nodes, edges)` contract.

## COBOL frontend (`frontends/cobol.py`)

### Preprocess
- Detect **fixed vs free format** (heuristic: any code in cols 1–6 that is digits, or a
  `*`/`-`/`/` in col 7 → fixed).
- Fixed-format: strip sequence area (cols 1–6) and identification area (cols 73–80);
  honor col-7 indicator (`*`/`/` = comment, `-` = continuation).
- **`COPY` expansion:** resolve copybook name against configured copybook dirs
  (default: repo-wide `.cpy` index), inline its text; minimal `REPLACING ==a== BY ==b==`.
  Record a `COPIES` edge (program → `Copybook`) even when the copybook is not found.

### Structure → AstNode
- Primary spine = **column-aware regex** (COBOL is regex-tractable: paragraph/section
  names start in Area A col 8 and end with `.`; statements live in Area B). This is the
  reliable path.
- **tree-sitter-cobol is an optional enhancement**, tried first when the grammar loads;
  on any failure, fall back to the regex spine. (Grammar is *not* in
  `tree_sitter_languages`; treat as best-effort.)
- Emit: `module`(program) → `function`(each PARAGRAPH; SECTION becomes a `function`
  with paragraph children) with `call` children for each `PERFORM <name>`,
  `CALL '<prog>'`, `GO TO <name>`. `metadata` carries `{"cobol_kind": "paragraph|section|program"}`.

### data_items → rules
- Parse `DATA DIVISION` level numbers (`01/05/.../88`), `REDEFINES`, `OCCURS`, `PIC`.
- **`88`-level condition names and `IF/EVALUATE` in PROCEDURE DIVISION are the encoded
  business rules** — surface them to `business_rule_extractor` via a new
  `_extract_cobol_candidates(source, path)` heuristic (natural-language statement +
  confidence), which then flows through the existing LLM enrichment + registry dedup.

### Neo4j node/edge additions
- Nodes: `CobolProgram, Section, Paragraph, Copybook, DataItem` (paragraphs/sections are
  emitted as generic call-graph `Function`-kind nodes so blast radius already traverses
  them; `Copybook`/`DataItem` are extra kinds).
- Edges: `PERFORMS, CALLS, COPIES, GOES_TO`.

## JCL frontend (`frontends/jcl.py`)  — Phase 2

- Parse `//name JOB`, `//step EXEC PGM=prog`, `//dd DD DSN=dataset`.
- Nodes: `JclJob, JclStep, Dataset`. Edges: `RUNS(step → CobolProgram)`,
  `USES_DATASET(step → Dataset)`, `SUBMITS(job → step)`.
- Extensions: `.jcl`, `.job`, and members detected by a `// ... JOB` first line.

## DB2 / CICS frontend (`frontends/mainframe_data.py`) — Phase 3

- **DB2:** `EXEC SQL ... END-EXEC` blocks inside COBOL → `READS/WRITES(program → Db2Table)`;
  standalone `CREATE TABLE` DDL (`.sql/.ddl`) → `Db2Table` nodes with columns.
- **CICS:** `EXEC CICS` verbs → `CicsTransaction` nodes; `STARTS/EXPOSES` edges to programs.

## Wiring

- `parser.py`: add a frontend **registry dispatch**. `parse_file`/`parse_directory`
  attach `frontend_language` so downstream can pick the frontend. Modern-lang behavior
  unchanged (DefaultFrontend).
- `orchestrator.build_knowledge_base`: after parse, for files whose language has a
  dedicated frontend, build nodes/edges via the frontend and merge into the graph write
  (alongside the existing `build_call_graph` for modern langs). Modules are persisted
  per program/copybook (reusing the step-4b `upsert_module` path added earlier).
- `business_rule_extractor.extract_rules`: dispatch COBOL files to the new heuristic.
- Priority, timeline, comprehension, gates: **unchanged** — they operate on the graph +
  modules + rules the frontends populate.

## Scale (millions of LOC)

- Per-file isolation already exists (one bad program never sinks a run).
- Add **content-hash skip**: unchanged files (by sha) are not re-parsed/re-embedded.
- Parse files in parallel (thread pool), bounded; copybook index built once per repo.

## Testing

- Unit: fixture COBOL program + copybook + JCL + DB2 DDL under `tests/fixtures/legacy/`.
  Assert preprocess (fixed-format strip, COPY inline), paragraph/PERFORM/CALL AstNode
  shape, JCL RUNS edges, EXEC SQL READS/WRITES, `88`-level rule candidates.
- Integration (live, opt-in): run `build_knowledge_base` on the fixture repo; assert
  Neo4j has program/paragraph/copybook/dataset/table nodes and the expected edges, and
  Postgres has module rows. Reuse the existing store/graph helpers.
- Regression: full existing suite (112) stays green — DefaultFrontend preserves behavior.

## Phasing

- **P1** COBOL programs + copybooks: preprocessor, regex spine, AstNode/call edges,
  `88`/IF rule candidates, module persistence. Frontend abstraction + registry land here.
- **P2** JCL + datasets: `RUNS/USES_DATASET`, cross-artifact blast radius.
- **P3** DB2 + CICS: `READS/WRITES` tables, CICS transactions.

Each phase is independently testable against Neo4j/Postgres/Qdrant.

## Risks

- **tree-sitter-cobol not bundled** → mitigated: the column-aware regex spine is the
  primary; tree-sitter is enhancement only.
- **Dialect variance** (IBM/GnuCOBOL/Micro Focus) → regex spine targets the common,
  well-standardized structural forms; deep dialect fidelity is a later ProLeap/GnuCOBOL
  frontend (out of scope here).
- **COPY resolution ambiguity** (copybooks across libraries) → best-effort index by
  member name; unresolved copies still recorded as `Copybook` nodes with `resolved=false`.

## Out of scope

- ProLeap/GnuCOBOL high-fidelity engine, PL/I, Natural/ADABAS, Assembler.
- Automated COBOL→modern transformation (that runs later on top of this understanding).
