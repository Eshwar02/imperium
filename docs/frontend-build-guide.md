# Imperium Frontend — Premium IDE Build Spec

**Date:** 2026-07-30
**Goal:** a premium, VS Code-class desktop-feeling web application that is the single
surface for the entire Imperium workflow — ingest a repo, explore it as a living
graph, watch the agents work, and drive every human-in-the-loop gate. Not a dashboard;
an **IDE for understanding and modernizing a codebase**.

---

## 0. What exists today

React + Vite + TypeScript scaffold in `frontend/`: a typed API client
(`src/api/client.ts`) and three stub pages (`GateA`, `GateB`, `StructureMap`). Backend
routes today: `ingest`, `analysis` (returns React-Flow-shaped `structure_map` +
`findings`), `gate-a`, `gate-b`, `clarifications`, `decisions`, `health`. This spec
supersedes the stubs — they become panels inside the IDE shell below.

---

## 1. Product principles

- **IDE, not pages.** A persistent shell (activity bar, dockable panels, editor area,
  bottom panel, status bar), not a set of routed full-screen pages. Everything is a
  panel the user can split, dock, and pin.
- **The graph is the hero.** The call/dependency graph is the primary way to navigate
  the system. Selecting a node drives every other panel (code, findings, rules, blast
  radius). This is the differentiator — invest here.
- **Everything is live.** Agent runs, analysis progress, and gate state stream in real
  time. The user watches agents reason and call tools, not a spinner.
- **Keyboard-first & fast.** Command palette (⌘K), fuzzy file/symbol jump, virtualized
  everything. Feels instant on a 100k-file repo.
- **Dark-first, premium.** VS Code-grade visual polish: consistent spacing, motion,
  focus rings, empty states, skeletons.

---

## 2. Shell & layout

```
┌───────────────────────────────────────────────────────────────────────┐
│  Title bar: repo picker · pipeline stepper · ⌘K palette · token/cost    │
├──┬────────────────────────┬───────────────────────────────────┬────────┤
│A │  Left dock             │  Editor / Graph area (tabs+split) │ Right  │
│c │  • Explorer (memory    │  • Graph Viewer                   │ dock   │
│t │    hierarchy tree)     │  • Code (Monaco)                  │ • Insp-│
│i │  • Findings            │  • Behavioral Diff (Monaco diff)  │  ector │
│v │  • Business Rules      │  • Timeline                       │ • Chat │
│i │  • Changesets          │  • Priority board                 │  (RKB) │
│t │  • Decisions/Audit     │                                   │        │
│y ├────────────────────────┴───────────────────────────────────┴────────┤
│  │  Bottom panel: Agent Activity (live) · Problems · Clarifications ·    │
│  │  Simulations · Token usage                                           │
├──┴──────────────────────────────────────────────────────────────────────┤
│  Status bar: backend health · active repo · current gate · run state    │
└───────────────────────────────────────────────────────────────────────┘
```

- **Docking:** use `dockview` (or `rc-dock`) for draggable/splittable/tabbed panels.
- **Command palette:** `kbar` — commands for ingest, run analysis, jump to symbol,
  open gate, toggle theme, focus node in graph.
- **Everything keyed by `repository_id`** in the URL so state is deep-linkable and
  refresh-safe.

---

## 3. The Graph Viewer (flagship feature)

The interactive view of the codebase's **multiple graph layers** (Neo4j, surfaced by
the backend). This is the centerpiece.

**Graph layers (switchable overlays over the same nodes):**
- **Call graph** — `CALLS` edges between functions/methods.
- **Dependency graph** — `DEPENDS_ON` between modules/packages.
- **API graph** — `EXPOSES` / `CONSUMES` endpoints (internal + external).
- **Data graph** — `READS` / `WRITES` between code and DB tables/columns.
- **Architecture graph** — the memory-hierarchy containment (`Domain → Module → File`).

A **layer switcher** toggles/combines layers; edges are colored/styled per relation
type with a legend. At enterprise scale the graph is huge, so the viewer must
**cluster by domain/module and lazily expand** — never render a million nodes at once.
Default view is the architecture/domain level; drill down into a domain to load its
call/data/API subgraph on demand (backed by paginated graph endpoints).

**Rendering engine:**
- **`@xyflow/react` (React Flow)** for curated/medium graphs — the backend already
  shapes `structure_map` as `{ nodes, edges }` for it. Rich custom nodes, animated
  edges, minimap, controls.
- For **very large** graphs (10k+ nodes) fall back to a WebGL engine —
  **`sigma.js` + `graphology`** or **Cytoscape.js** — with the same interaction model.
  Decide at load time from node count.

**Must-have interactions:**
- Zoom/pan, minimap, fit-to-view, fullscreen.
- **Layouts:** force-directed (default), hierarchical/layered (dagre/ELK), and
  domain-clustered — cluster by the memory hierarchy (`Domain → Module → File →
  Function`). Toggle live.
- **Node semantics via encoding:** color = category/risk, size = transformation
  priority score, badge = AI-authorship %, ring = flagged-for-review / low
  comprehension. A legend explains it.
- **Blast radius:** select a node → highlight everything that depends on it (dim the
  rest). Backed by `graph.blast_radius`. This is the "what breaks if I change this"
  view — central to the two human gates.
- **Focus + drill-down:** expand/collapse clusters, isolate a subgraph, "show only
  paths between A and B."
- **Search & filter:** find node by name/symbol; filter by category, risk, priority
  threshold, domain.
- **Selection is global:** selecting a node updates the Inspector, opens its source in
  Monaco, filters Findings/Rules to it, and scrolls the Timeline to its history.
- **Overlays (toggle):** findings heatmap, priority heatmap, business-rule density,
  churn (from timeline), comprehension-drift risk.

**Backend needs:** a dedicated graph endpoint beyond the analysis `structure_map`
(e.g. `GET /api/graph/:id` → full `repo_graph`, plus `GET /api/graph/:id/blast/:nodeId`).
`rkb/graph.py` already has `repo_graph`, `blast_radius`, `query_dependents`, `get_node`
— they need routes.

---

## 4. Code & diff viewing (Monaco)

- **`@monaco-editor/react`** for a genuine editor experience: syntax highlighting,
  minimap, folding, symbol outline, go-to-definition (wired to the call graph),
  find-in-file. **Read-only** for source; annotations layered on top (findings,
  business rules, AI-authorship gutter markers).
- **Behavioral Diff (Gate B):** Monaco **diff editor** showing old vs. proposed code
  side by side, annotated with the simulation's predicted behavior change and
  confidence. Inline decorations for "rule preserved / rule at risk."
- Deep-link: clicking a finding location (`file.py:12`) or a graph node opens the file
  at that line.

---

## 5. Panels (each a first-class surface)

### Explorer — Memory Hierarchy tree
Virtualized tree over `Repository → Domain → Module → File → Function`. Lazy-load
children. Each node shows priority/risk/AI-% chips. Drives the graph and editor.
*(Backend: needs a hierarchy/tree endpoint; today derivable from modules + graph.)*

### Analysis / Findings
Grouped by `category` (security / performance / modernization / integration /
documentation). Confidence bars, location chips, "focus in graph." Live-updates while a
run is in progress. Source: `GET /api/analysis/:id` (poll or stream).

### Business Rule Registry
Table + detail: statement, confidence, verified state, linked locations, linked
decisions. Low-confidence rules surface as **Clarifications** (inbox) — answer via
`POST /api/clarifications/:id/answer`. *(List route needed; store has the data.)*

### Transformation Priority board
Ranked list/kanban of what to modernize first, with the score's factor breakdown
(blast radius, rule density, AI-authorship, churn). Sort/filter; select → graph focus.
*(Backend: `get_priorities` exists; needs a route.)*

### Changesets
The manifest of files a transformation touches, grouped by module/domain/call-graph
proximity — not a flat list. Tree + graph overlay. *(store `get_changesets`; needs route.)*

### Timeline
Narrative git-history view — churn, refactors, incident-driven changes — as an
interactive timeline (visx). Scrub to see the repo evolve; select a module to filter.
*(store `get_timeline`; needs route.)*

### Simulations
Per transformation: expected-old → predicted-new → diff → confidence/safety score.
Below-threshold simulations are flagged and block the gate. Opens into the Monaco diff.
*(store `get_simulations`; needs route.)*

### Decisions / Audit
Append-only timeline of every agent decision and human approval/rejection: who, when,
gate, verdict, note. `GET /api/decisions/:id`. Read-only, exportable.

### Comprehension checks
Post-merge non-blocking quizzes per owner/module, and the per-module comprehension
score vs. AI-authorship %. Surfaces comprehension-drift risk back into the graph.
*(Backend: needs routes to fetch/answer checks.)*

---

## 6. Gate A & Gate B — the HITL workflow

The reason the product exists. Both are guided review flows, not just forms.

- **Gate A (approve findings):** review findings per category (with graph + code
  context and any clarifications resolved), vote `approve | reject | defer` with a note.
  `POST /api/gate-a`. Only approved categories advance.
- **Gate B (behavioral diff review):** for each proposed change, review the Monaco
  behavioral diff + simulation confidence, then vote. `POST /api/gate-b`. Approve →
  merges to integration.
- A **pipeline stepper** in the title bar always shows where the repo is
  (ingest → analyze → Gate A → simulate → Gate B → docs) and what's blocking.

---

## 7. Agent Activity (live orchestration monitor)

A real-time bottom-panel stream of the multi-agent run: which agent is active, its
role/model (per-agent routing), the **tools it calls** (agents are tool-using —
`search_memory`, `blast_radius`, `read_source`, …), tool results, and its reasoning.
Think "LangGraph run trace" as a first-class UI.

**These runs are long-running** (enterprise codebases take a long time), so the UI must
treat a run as a durable, resumable entity — not a request:
- **Progress at scale:** overall % plus per-stage and per-module fan-out progress
  (agents map-reduce over the module hierarchy), with counts (modules analyzed / total).
- **Durable & resumable:** a run has an id and survives refresh/disconnect; reconnect
  re-attaches to the live stream and backfills missed events. Pause / resume / cancel.
- **Gate interrupts:** when the run hits Gate A/B it **suspends** (a LangGraph
  interrupt) and the UI surfaces the gate; approving resumes the same run.
- **History:** list past/active runs per repo, each replayable.

**Backend needs:** streaming — **SSE** (`GET /api/runs/:id/events`, `text/event-stream`)
emitting agent/tool/token/progress events — plus run lifecycle routes
(`POST /api/runs/:id/{start,cancel}`, `GET /api/runs/:id`). Backed by the Phase 3
LangGraph orchestration with a **Postgres checkpointer** (durable runs + gate interrupts).

### 7a. Change dashboard — "what & why" (per-edit view)

The raw event trace answers *"what is the agent doing?"*; a reviewer also needs *"what
part of the code is changing, and why?"* at a glance. Alongside the low-level activity
log, render a **Change dashboard** that turns the agent's edit/write tool-calls into a
readable, live feed of file-level changes:

- A **"now" line** + pulsing live indicator: the current action ("Editing `app.py`",
  "Locating `grep …`").
- Running **counts**: edits / writes / lookups.
- **One card per change**, newest first:
  - **EDIT** — the target file + a mini `- old` / `+ new` snippet of the exact hunk
    (from the `edit_file` tool args); on selection, deep-link into the Monaco diff.
  - **WRITE** — the file + a preview of new content (`write_file`).
  - **LOOK** — the locate steps that led here (grep / find-definition / read / memory /
    blast-radius), shown lighter so the reasoning path is visible but not noisy.
  - Each edit/write card carries a **`why:`** line — the rationale for that file pulled
    from the **multi-file plan** (`plan` event: `{file, action, rationale}`), so *what
    changed* and *why* sit together instead of in separate panels.

**This is already prototyped** in the throwaway `frontend-dev/` harness (a
three-column: controls · output · "Process — what & why"), driven entirely by the
CodeAgent SSE stream below — port that dashboard into the IDE's right dock / Agent
Activity panel.

**Backend (shipped):** the CodeAgent coding endpoints already emit exactly the events
this dashboard consumes:
- `POST /api/code/:id/plan` → `{steps:[{file, action, rationale}], summary}` (the "why").
- `POST /api/code/:id/stream` (SSE) → `start` → `plan` → `tool_call` /`tool_result` /
  `message` → `tests` → `done` events. `tool_call` args for `edit_file` / `write_file`
  carry the file path and the old/new (or content) — the "what".
- `POST /api/code/:id` → non-streaming `{applied, summary, branch, files_changed, diff,
  plan, tests}` for a one-shot result.

---

## 8. RKB Chat / Copilot (right dock)

A conversational panel to query the whole-org memory: "where is auth enforced?", "why
was billing rewritten?". Runs semantic search over Qdrant + the graph and streams an
answer with **cited nodes/files** that are clickable into the graph and editor.
*(Backend: needs a `POST /api/chat/:id` (streaming) over `rkb.embeddings.search` + graph.)*

---

## 9. Token usage / cost

Status-bar summary + a bottom-panel breakdown per agent role (input/output/total
tokens, calls) from the Phase 1 accounting (`llm.client.get_token_usage`). *(Backend:
needs `GET /api/usage/:id`; the data is already accumulated in-process.)*

---

## 10. Cross-cutting engineering

| Concern | Choice |
|--------|--------|
| Data fetching | **TanStack Query** — caching, polling, retries, loading/error states |
| Client state | **Zustand** (selection, layout, run state) |
| Routing | **React Router**, `repository_id` in path |
| UI kit | **Tailwind + shadcn/ui** (Radix primitives) |
| Docking | **dockview** / rc-dock |
| Editor/diff | **Monaco** (`@monaco-editor/react`) |
| Graph | **React Flow** + **sigma.js/graphology** (large) |
| Command palette | **kbar** |
| Virtualization | **@tanstack/react-virtual** |
| Charts | **visx** (timeline, priority, cost) |
| Real-time | **SSE** (EventSource); WebSocket if bidirectional needed |
| Theming | dark-first, design tokens, light theme parity |
| Types | mirror `api/schemas.py`; later generate from FastAPI OpenAPI |
| Testing | Vitest + Testing Library; Playwright for the core flow |

**Structure:** `src/shell/`, `src/panels/<name>/`, `src/graph/`, `src/editor/`,
`src/api/` (typed hooks per resource), `src/store/`, `src/lib/`. One panel = one folder,
one clear responsibility.

---

## 11. Backend endpoints this frontend requires

Everything below is "data exists in `rkb/store.py` / `rkb/graph.py` / `llm.client`, but
no HTTP route yet." Building the premium frontend means adding these (small FastAPI
routes over existing functions):

- `GET /api/graph/:id?layer=call|dependency|api|data|arch&domain=…` (paginated, per-layer,
  drill-down by domain/module) · `GET /api/graph/:id/blast/:nodeId`
- `GET /api/hierarchy/:id` (memory-hierarchy tree)
- `GET /api/runs/:id` · `POST /api/runs/:id/start|cancel` · `GET /api/runs/:id/events` (SSE)
- `GET /api/business-rules/:id`
- `GET /api/priorities/:id` · `GET /api/changesets/:id` · `GET /api/simulations/:id`
- `GET /api/timeline/:id`
- `GET /api/comprehension/:id` (+ answer route)
- `GET /api/usage/:id` (token accounting)
- `GET /api/runs/:id/events` (SSE agent/tool/token stream)
- `POST /api/chat/:id` (streaming RKB Q&A)

Ship the frontend panel and its backend route together, feature by feature.

---

## 12. Build order (each vertical slice is demo-able)

1. **IDE shell** — dock layout, activity bar, command palette, theming, status bar,
   repo picker + pipeline stepper.
2. **Graph Viewer v1** — React Flow over `structure_map`, selection → Inspector.
3. **Code + Explorer** — Monaco read-only + memory-hierarchy tree, graph↔editor link.
4. **Analysis + Findings** — run + poll/stream, findings overlays on the graph.
5. **Gate A + Clarifications** — the first full HITL loop.
6. **Graph Viewer v2** — blast radius, layouts, overlays, large-graph engine.
7. **Simulations + Gate B** — Monaco behavioral diff + confidence, second HITL loop.
8. **Agent Activity (live)** — SSE run trace with tool calls.
9. **Timeline · Priority · Changesets · Decisions · Comprehension** panels.
10. **RKB Chat + Token/Cost** — copilot and cost visibility.

---

## Definition of done

A user opens Imperium, points it at a repo, and watches analysis stream in. They
navigate the system as an interactive graph — clicking a module to see its code,
findings, business rules, blast radius, and history side by side. They resolve
clarifications, vote Gate A, review behavioral diffs in a real diff editor, vote Gate B,
and watch the agents reason and call tools live — all in one fast, dark, VS Code-class
workspace, deep-linkable by `repository_id`, with token cost always visible and no dead
spinners.
