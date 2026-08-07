# Architecture Map — full-screen, API-labeled component graph

**Date:** 2026-08-07
**Status:** Approved (design)

## Problem

The current graph (`StructureMapPanel`) renders the ingested repo's raw
code-dependency graph flat, cramped inside the left "Imperium Intelligence"
accordion. It's hard to read and doesn't convey how the application actually
works. We want a **full-screen architecture/flow map**: pages/components as
nodes, arrows between them, and each arrow labeled with the **API method it
uses** (e.g. `api.chat() → POST /api/chat/{id}`), so the whole working of the
app — plus its API surface — is legible on a single screen.

Reference mental model: the bearbot app, where "New Chat" leads to the new-chat
page and "Daily Brief" leads to its page, with the connecting arrows annotated
by the API calls behind each transition.

## Decisions (from brainstorming)

- **Data source:** Hybrid — analysis provides the base graph; a curated overlay
  can add/rename/group nodes and pin arrow labels + positions.
- **Arrow label:** Both — `client method → HTTP method + route`
  (e.g. `api.chat() → POST /api/chat/{id}`). Long labels truncate with full
  text on hover.
- **Home:** A full-screen editor tab only. The cramped left-panel Structure Map
  is removed; a launcher button + command-palette entry open the tab.
- **Curated overlay lives in the frontend** (`src/lib/graphOverrides.ts`).

## Architecture

### 1. Shell integration
- Extend `OpenEditor` (WorkbenchContext) with optional `kind?: "file" | "graph"`
  (default `"file"`). `EditorArea` renders the map component when
  `kind === "graph"`, otherwise Monaco as today. Tab renders as `◈ Architecture Map`.
- Remove the `Structure Map` section from `IntelView` (SideBar). Replace with a
  one-line **"Open Architecture Map ⬲"** launcher button that calls
  `openFile({ kind: "graph", repoId, path: "::arch-map", name: "Architecture Map" })`.
  (`path` is a synthetic, stable key so tab de-dup/close logic is unchanged.)
- Add a command-palette entry `View: Architecture Map` (App.tsx command list)
  that does the same.
- `StructureMapPanel.tsx` is deleted.

### 2. Data — hybrid
- **Base from analysis:** the map fetches `/api/graph/{id}?layer=api` (the
  `EXPOSES`/`CONSUMES` layer between files and endpoints) and `?layer=arch`
  (component/page-level nodes), merging them.
- **Backend change (small):** `repo_graph` and `layer_graph` in
  `backend/imperium/rkb/graph.py` currently `RETURN … type(r) AS type` and drop
  edge properties. Change the Cypher to also return `properties(r) AS props` and
  merge those into each edge dict. This lets any `method`/`route`/`label`
  metadata on an edge reach the client. Node payloads already include `kind`,
  `name`, and file/route props.
- **Frontend types:** `GraphEdge` gains optional `method?`, `route?`, `label?`.
- **Curated overlay** (`src/lib/graphOverrides.ts`): an optional, per-repo
  (keyed by repo id or `"*"`) object that can:
  - rename a node and/or assign it a `group` ("page" | "component" | "api" | "data");
  - pin an edge label (`"api.chat() → POST /api/chat/{id}"`);
  - pin node positions.
  Empty by default. It is a pure data module — no side effects — so overrides are
  applied by a pure merge function (testable). Guarantees the demo repo looks
  right even where analysis output is thin.

### 3. Rendering
- Custom React Flow node = a **component card**: kind/group icon + name +
  subtitle (file path or route), styled with the existing theme tokens (`t.*`).
- **Layered left-to-right layout** computed in-app (no dagre dependency): nodes
  grouped into columns by resolved group — Pages/Components → API/Endpoints →
  Data — and stacked vertically within a column. Curated positions, when present,
  override the computed position. Extracted as a pure function
  `layoutNodes(nodes, overrides)` for testability.
- **Edge label** resolution (pure function `edgeLabel(edge, overrides)`):
  `override.label ?? (edge.method && edge.route ? \`${method} → ${route}\` :
  route ?? method ?? type)`. Rendered as a small chip on the edge; CSS-truncated
  with the full string in a `title`/tooltip on hover.
- Full React Flow controls (zoom / pan / fit-view) since the map is now
  full-screen.

### 4. Interaction
- Click a node card → `openFile` the underlying file in a normal editor tab
  (when the node carries a file path).
- Hover/click an edge → tooltip with the full `method → route` label.
- Empty / error / loading states reuse the existing `Empty`/`Center` patterns.

## Components & boundaries
- `src/components/workbench/ArchitectureMap.tsx` — the full-screen map (fetch,
  layout, render). One purpose: turn graph data + overrides into a React Flow
  canvas.
- `src/lib/graphLayout.ts` — pure helpers: `layoutNodes`, `edgeLabel`,
  `applyOverrides`. No React, fully unit-testable.
- `src/lib/graphOverrides.ts` — curated data only.
- `EditorArea.tsx` — gains a `kind` switch. `WorkbenchContext.tsx` — `OpenEditor.kind`.
- Backend: `graph.py` Cypher returns edge properties.

## Testing
- **Backend:** unit test that `layer_graph` / `repo_graph` include edge
  properties in returned edges (mock Neo4j driver/session, mirroring existing
  graph tests).
- **Frontend:** `tsc -b` clean. Pure-function tests for `edgeLabel` (all
  fallback branches) and `layoutNodes` (grouping into columns, override wins).
  Since there is no frontend test runner yet, these run as a small standalone
  Node script under the job tmp dir, asserting the pure helpers — same approach
  used to verify the chat SSE fix.

## Out of scope (YAGNI)
- Editing the graph from the UI. Persisting curated overrides to the backend.
- Auto-layout via dagre or physics simulation.
- Multi-repo / cross-repo maps.
