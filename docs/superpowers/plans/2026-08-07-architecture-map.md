# Architecture Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the cramped left-panel structure graph with a full-screen "Architecture Map" editor tab whose arrows are labeled with the API methods (`api.chat() → POST /api/chat/{id}`) connecting pages/components.

**Architecture:** Backend graph reads start returning edge properties. The frontend fetches the `api` + `arch` graph layers, merges a curated overrides module, lays nodes out in kind-columns via pure helpers, and renders them as component cards in a React Flow canvas hosted inside `EditorArea` as a new `kind: "graph"` tab. The old `StructureMapPanel` is deleted.

**Tech Stack:** FastAPI + Neo4j (backend), React + TypeScript + reactflow + Vite (frontend).

## Global Constraints

- Frontend and backend are both tracked + pushed to `main` (commit granularly, serially).
- No new frontend dependencies (reactflow already present; no dagre).
- Theme tokens come from `src/theme.ts` (`t.bg`, `t.bgElev`, `t.border`, `t.text`, `t.textDim`, `t.accent`, `t.sans`, `t.mono`, `t.red`, `t.green`, `t.yellow`).
- Backend tests run under `.venv` with `python -m pytest`; frontend has no test runner — pure helpers are verified with a standalone Node script under `$CLAUDE_JOB_DIR/tmp` and `npx tsc -b`.

---

### Task 1: Backend — graph reads return edge properties

**Files:**
- Modify: `backend/imperium/rkb/graph.py` (`repo_graph` ~100-117, `layer_graph` ~120-148)
- Test: `backend/tests/test_graph_edge_props.py` (create)

**Interfaces:**
- Produces: `repo_graph(rid)` / `layer_graph(rid, rels)` each return `{"nodes": [...], "edges": [{"source","target","type", **edge_props}]}` — edge dicts now include any Neo4j relationship properties (e.g. `method`, `route`, `label`) flattened in.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_graph_edge_props.py
"""layer_graph / repo_graph must surface relationship properties on edges."""
from __future__ import annotations

import contextlib

import imperium.rkb.graph as graph


class _Rec(dict):
    """A stand-in for a neo4j Record: dict access + dict() both work."""


class _Session:
    def __init__(self, edge_records, node_records):
        self._edge_records = edge_records
        self._node_records = node_records

    def run(self, query, **_):
        # First RETURN with `type(r)` is the edge query; the other is nodes.
        if "type(r)" in query:
            return iter(self._edge_records)
        return iter(self._node_records)


class _Driver:
    def __init__(self, session):
        self._session = session

    @contextlib.contextmanager
    def session(self):
        yield self._session


def test_layer_graph_flattens_edge_properties(monkeypatch):
    edge = _Rec(source="fileA", target="epChat", type="CONSUMES",
                props={"method": "api.chat()", "route": "POST /api/chat/{id}"})
    node = _Rec(n={"id": "fileA", "kind": "File", "name": "chat.ts"})
    monkeypatch.setattr(graph, "_driver", lambda: _Driver(_Session([edge], [node])))

    out = graph.layer_graph("repo-1", ["CONSUMES"])
    e = out["edges"][0]
    assert e["source"] == "fileA" and e["target"] == "epChat" and e["type"] == "CONSUMES"
    assert e["method"] == "api.chat()"
    assert e["route"] == "POST /api/chat/{id}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_graph_edge_props.py -q`
Expected: FAIL — `KeyError: 'method'` (props not flattened yet).

- [ ] **Step 3: Implement — return + flatten `properties(r)`**

In `layer_graph`, change the edges query and materialization:

```python
        edges_res = session.run(
            f"""
            MATCH (a {{repository_id: $rid}})-[r:{rel_pattern}]->(b {{repository_id: $rid}})
            RETURN a.id AS source, b.id AS target, type(r) AS type, properties(r) AS props
            """,
            rid=repository_id,
        )
        edges = [_edge_dict(record) for record in edges_res]
```

In `repo_graph`, change identically:

```python
        edges_res = session.run(
            """
            MATCH (a {repository_id: $rid})-[r]->(b {repository_id: $rid})
            RETURN a.id AS source, b.id AS target, type(r) AS type, properties(r) AS props
            """,
            rid=repository_id,
        )
        nodes = [dict(record["n"]) for record in nodes_res]
        edges = [_edge_dict(record) for record in edges_res]
```

Add a module-level helper near the top of the reads section (after `_driver`):

```python
def _edge_dict(record) -> dict:
    """Flatten a (source, target, type, props) edge record into one dict."""
    edge = {"source": record["source"], "target": record["target"], "type": record["type"]}
    edge.update(record["props"] or {})
    return edge
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_graph_edge_props.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full backend suite (no regressions)**

Run: `cd backend && source .venv/bin/activate && python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/imperium/rkb/graph.py backend/tests/test_graph_edge_props.py
git commit -m "feat(graph): surface relationship properties on graph-read edges"
git push origin main
```

---

### Task 2: Frontend — edge types + pure layout/label helpers + overrides module

**Files:**
- Modify: `frontend/src/api/client.ts:17` (`GraphEdge`)
- Create: `frontend/src/lib/graphLayout.ts`
- Create: `frontend/src/lib/graphOverrides.ts`
- Test: standalone Node script (not committed) under `$CLAUDE_JOB_DIR/tmp`

**Interfaces:**
- Consumes: `GraphNode { id; name?; kind?; [k]: unknown }` from `client.ts`.
- Produces:
  - `GraphEdge { source; target; type; method?; route?; label? }`.
  - `type Group = "page" | "component" | "api" | "data" | "other"`.
  - `interface NodeOverride { name?; group?; position?: { x; y } }`.
  - `interface RepoOverrides { nodes?: Record<string, NodeOverride>; edges?: Record<string, string> }` (edge key = `"source->target"`).
  - `overridesFor(repoId: string): RepoOverrides`.
  - `groupOf(node: GraphNode, ov?: NodeOverride): Group`.
  - `edgeLabel(edge: GraphEdge, ov?: string): string`.
  - `layoutNodes(nodes: GraphNode[], ov: RepoOverrides): Record<string, { x; y }>`.

- [ ] **Step 1: Update `GraphEdge` type**

In `frontend/src/api/client.ts` replace line 17:

```ts
export interface GraphEdge { source: string; target: string; type: string; method?: string; route?: string; label?: string }
```

- [ ] **Step 2: Create the overrides module**

```ts
// frontend/src/lib/graphOverrides.ts
// Curated layer over the analyzed graph: rename/group nodes, pin arrow labels
// and positions. Keyed by repository id, with "*" applied to every repo.
export type Group = "page" | "component" | "api" | "data" | "other";

export interface NodeOverride { name?: string; group?: Group; position?: { x: number; y: number } }
export interface RepoOverrides {
  nodes?: Record<string, NodeOverride>;
  edges?: Record<string, string>; // "source->target" -> label
}

const OVERRIDES: Record<string, RepoOverrides> = {
  "*": {},
};

export function overridesFor(repoId: string): RepoOverrides {
  const base = OVERRIDES["*"] ?? {};
  const repo = OVERRIDES[repoId] ?? {};
  return {
    nodes: { ...(base.nodes ?? {}), ...(repo.nodes ?? {}) },
    edges: { ...(base.edges ?? {}), ...(repo.edges ?? {}) },
  };
}
```

- [ ] **Step 3: Create the pure layout/label helpers**

```ts
// frontend/src/lib/graphLayout.ts
// Pure, DOM-free helpers that turn analyzed graph data + curated overrides into
// positions and edge labels. Unit-testable in isolation.
import type { GraphNode, GraphEdge } from "../api/client";
import type { Group, NodeOverride, RepoOverrides } from "./graphOverrides";

const COLUMN: Record<Group, number> = { page: 0, component: 1, api: 2, data: 3, other: 4 };
const COL_W = 260;
const ROW_H = 110;

/** Resolve a node's group: explicit override wins, else inferred from kind. */
export function groupOf(node: GraphNode, ov?: NodeOverride): Group {
  if (ov?.group) return ov.group;
  const k = (node.kind ?? "").toLowerCase();
  if (k.includes("page") || k.includes("route") || k.includes("view")) return "page";
  if (k.includes("component") || k.includes("module") || k.includes("file")) return "component";
  if (k.includes("endpoint") || k.includes("api")) return "api";
  if (k.includes("table") || k.includes("db") || k.includes("store")) return "data";
  return "other";
}

/** Arrow label: pinned override, else `method → route`, else route/method/type. */
export function edgeLabel(edge: GraphEdge, ov?: string): string {
  if (ov) return ov;
  if (edge.label) return edge.label;
  if (edge.method && edge.route) return `${edge.method} → ${edge.route}`;
  return edge.route ?? edge.method ?? edge.type;
}

/** Position map keyed by node id: kind-columns, stacked vertically; override wins. */
export function layoutNodes(nodes: GraphNode[], ov: RepoOverrides): Record<string, { x: number; y: number }> {
  const rowByCol: Record<number, number> = {};
  const pos: Record<string, { x: number; y: number }> = {};
  for (const n of nodes) {
    const o = ov.nodes?.[n.id];
    if (o?.position) { pos[n.id] = o.position; continue; }
    const col = COLUMN[groupOf(n, o)];
    const row = rowByCol[col] ?? 0;
    rowByCol[col] = row + 1;
    pos[n.id] = { x: col * COL_W, y: row * ROW_H };
  }
  return pos;
}
```

- [ ] **Step 4: Write + run a standalone verification script**

```bash
cat > "$CLAUDE_JOB_DIR/tmp/layout.mjs" <<'EOF'
// Mirrors graphLayout.ts logic to verify branch behavior without a bundler.
const COLUMN = { page:0, component:1, api:2, data:3, other:4 };
const groupOf = (n, o) => o?.group ?? ((k=(n.kind||'').toLowerCase()) =>
  k.includes('page')||k.includes('route')||k.includes('view') ? 'page'
  : k.includes('component')||k.includes('module')||k.includes('file') ? 'component'
  : k.includes('endpoint')||k.includes('api') ? 'api'
  : k.includes('table')||k.includes('db')||k.includes('store') ? 'data' : 'other')();
const edgeLabel = (e, ov) => ov ?? e.label ?? (e.method && e.route ? `${e.method} → ${e.route}` : (e.route ?? e.method ?? e.type));

// edgeLabel branches
console.assert(edgeLabel({type:'CONSUMES', method:'api.chat()', route:'POST /api/chat/{id}'}) === 'api.chat() → POST /api/chat/{id}', 'method→route');
console.assert(edgeLabel({type:'CONSUMES'}, 'PINNED') === 'PINNED', 'override wins');
console.assert(edgeLabel({type:'EXPOSES'}) === 'EXPOSES', 'type fallback');
// groupOf
console.assert(groupOf({kind:'ApiEndpoint'}) === 'api', 'api group');
console.assert(groupOf({kind:'File'}, {group:'page'}) === 'page', 'override group');
console.log('OK');
EOF
node "$CLAUDE_JOB_DIR/tmp/layout.mjs"
```

Expected: prints `OK` with no assertion errors.

- [ ] **Step 5: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: exit 0 (helpers may be unused until Task 4 — that is fine, they are exported).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/lib/graphLayout.ts frontend/src/lib/graphOverrides.ts
git commit -m "feat(ui): graph edge fields + pure layout/label/overrides helpers"
git push origin main
```

---

### Task 3: Workbench — `kind` on editor tabs, map host in EditorArea

**Files:**
- Modify: `frontend/src/context/WorkbenchContext.tsx:8-12` (`OpenEditor`)
- Modify: `frontend/src/components/workbench/EditorArea.tsx` (tab icon + body switch)

**Interfaces:**
- Consumes: `ArchitectureMap` default export from Task 4 (`{ repoId: string }` prop). Until Task 4 lands, EditorArea imports it — do Task 3 and Task 4 together before typecheck, or stub. This plan orders Task 4's file first in the shared commit (see Task 4 Step 6).
- Produces: `OpenEditor { repoId; path; name; kind?: "file" | "graph" }`.

- [ ] **Step 1: Add `kind` to `OpenEditor`**

Replace `frontend/src/context/WorkbenchContext.tsx:8-12`:

```ts
export interface OpenEditor {
  repoId: string;
  path: string; // repo-relative, or a synthetic key like "::arch-map"
  name: string;
  kind?: "file" | "graph";
}
```

- [ ] **Step 2: Switch the tab icon + body in EditorArea**

In `frontend/src/components/workbench/EditorArea.tsx`, add the import at top:

```ts
import ArchitectureMap from "./ArchitectureMap";
```

Replace the tab-icon line (currently `<span>{fileIcon(e.name)}</span>`) with:

```tsx
              <span>{e.kind === "graph" ? "◈" : fileIcon(e.name)}</span>
```

Replace the body block `{active && (() => { … })()}` so graph tabs render the map:

```tsx
        {active && active.kind === "graph" && <ArchitectureMap repoId={active.repoId} />}
        {active && active.kind !== "graph" && (() => {
          const st = cache[active.path];
          if (!st || st.loading) return <Center>Loading {active.name}…</Center>;
          if (st.error) return <Center color={t.red}>Failed to open: {st.error}</Center>;
          if (st.binary) return <Center>Binary file — cannot display.</Center>;
          return (
            <Editor
              key={active.path}
              height="100%"
              theme="vs-dark"
              path={active.path}
              defaultLanguage={monacoLanguage(active.name)}
              value={st.content}
              options={{
                readOnly: true, fontSize: 13, minimap: { enabled: true },
                scrollBeyondLastLine: false, automaticLayout: true,
                fontFamily: "'JetBrains Mono', 'SF Mono', Menlo, monospace",
                renderWhitespace: "selection",
              }}
            />
          );
        })()}
```

Also guard the content fetch effect so it skips graph tabs — replace the effect's early return:

```tsx
    if (!active || active.kind === "graph") return;
```

And guard the breadcrumb so it hides for graph tabs — replace `{active && (` with:

```tsx
      {active && active.kind !== "graph" && (
```

- [ ] **Step 3: (typecheck deferred to Task 4)** — EditorArea now imports `ArchitectureMap`, created in Task 4. Proceed to Task 4, then typecheck.

- [ ] **Step 4: Commit (with Task 4)** — see Task 4 Step 6 (these two land together).

---

### Task 4: ArchitectureMap component

**Files:**
- Create: `frontend/src/components/workbench/ArchitectureMap.tsx`

**Interfaces:**
- Consumes: `api.graph`, `overridesFor`, `layoutNodes`, `edgeLabel`, `groupOf`, `useWorkbench().openFile`, theme `t`.
- Produces: `export default function ArchitectureMap({ repoId }: { repoId: string })`.

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/workbench/ArchitectureMap.tsx
// Full-screen architecture/flow map: component cards laid out in kind-columns,
// arrows labeled with the API method → route that connects them.
import { useMemo } from "react";
import ReactFlow, { Background, Controls, type Node, type Edge } from "reactflow";
import "reactflow/dist/style.css";
import { useAsync } from "../../hooks";
import { api, type GraphNode } from "../../api/client";
import { overridesFor } from "../../lib/graphOverrides";
import { layoutNodes, edgeLabel, groupOf } from "../../lib/graphLayout";
import { useWorkbench } from "../../context/WorkbenchContext";
import { t } from "../../theme";

const GROUP_ICON: Record<string, string> = { page: "▧", component: "◻", api: "◈", data: "▤", other: "•" };

export default function ArchitectureMap({ repoId }: { repoId: string }) {
  const { openFile } = useWorkbench();
  const ov = useMemo(() => overridesFor(repoId), [repoId]);

  // Merge the API layer (arrows we label) with the arch layer (component/page nodes).
  const { data, loading, error } = useAsync(async () => {
    const [apiL, archL] = await Promise.all([
      api.graph(repoId, "api"),
      api.graph(repoId, "arch"),
    ]);
    const nodeById = new Map<string, GraphNode>();
    for (const n of [...archL.nodes, ...apiL.nodes]) nodeById.set(n.id, n);
    return { nodes: [...nodeById.values()], edges: [...apiL.edges, ...archL.edges] };
  }, [repoId]);

  const pos = useMemo(() => (data ? layoutNodes(data.nodes, ov) : {}), [data, ov]);

  const nodes: Node[] = useMemo(
    () =>
      (data?.nodes ?? []).map((n) => {
        const o = ov.nodes?.[n.id];
        const g = groupOf(n, o);
        return {
          id: n.id,
          position: pos[n.id] ?? { x: 0, y: 0 },
          data: { label: `${GROUP_ICON[g]}  ${o?.name ?? n.name ?? n.id}`, path: (n as { path?: string }).path },
          style: {
            background: t.bgElev, color: t.text, border: `1px solid ${t.border}`,
            borderRadius: 8, fontSize: 12, fontFamily: t.sans, padding: "8px 10px", minWidth: 150,
          },
        };
      }),
    [data, pos, ov],
  );

  const edges: Edge[] = useMemo(
    () =>
      (data?.edges ?? []).map((e, i) => {
        const label = edgeLabel(e, ov.edges?.[`${e.source}->${e.target}`]);
        return {
          id: `${e.source}-${e.target}-${i}`,
          source: e.source, target: e.target, label,
          labelShowBg: true,
          style: { stroke: t.border },
          labelStyle: { fill: t.text, fontSize: 10, fontFamily: t.mono },
          labelBgStyle: { fill: t.bg },
        };
      }),
    [data, ov],
  );

  if (loading && !data) return <Center>Loading architecture map…</Center>;
  if (error) return <Center color={t.red}>Error: {error}</Center>;
  if (!nodes.length) return <Center>No graph data for this repository yet.</Center>;

  return (
    <div style={{ width: "100%", height: "100%", background: t.bg }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        onNodeClick={(_, node) => {
          const p = (node.data as { path?: string }).path;
          if (p) openFile({ repoId, path: p, name: p.split("/").pop() ?? p });
        }}
      >
        <Background color={t.border} gap={18} />
        <Controls />
      </ReactFlow>
    </div>
  );
}

function Center({ children, color = t.textDim }: { children: React.ReactNode; color?: string }) {
  return <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color, fontSize: 13 }}>{children}</div>;
}
```

- [ ] **Step 2: Update `api.graph` to accept a layer**

In `frontend/src/api/client.ts`, replace the `graph` line:

```ts
  graph: (id: string, layer = "all") =>
    get<{ nodes: GraphNode[]; edges: GraphEdge[] }>(`/api/graph/${id}?layer=${layer}`),
```

- [ ] **Step 3: Verify `useAsync` supports an async factory**

Run: `cd frontend && grep -n "export function useAsync" src/hooks.ts`
Expected: a generic `useAsync<T>(factory: () => Promise<T>, deps)` — the map passes an `async () => …`. If the signature differs, adapt the call to match; do not change `hooks.ts`.

- [ ] **Step 4: Typecheck (Tasks 3+4 together)**

Run: `cd frontend && npx tsc -b`
Expected: exit 0.

- [ ] **Step 5: Build**

Run: `cd frontend && npm run build`
Expected: Vite build succeeds.

- [ ] **Step 6: Commit (Tasks 3 + 4)**

```bash
git add frontend/src/context/WorkbenchContext.tsx frontend/src/components/workbench/EditorArea.tsx frontend/src/components/workbench/ArchitectureMap.tsx frontend/src/api/client.ts
git commit -m "feat(ui): full-screen Architecture Map editor tab with API-labeled arrows"
git push origin main
```

---

### Task 5: Entry points — launcher button + command, delete old panel

**Files:**
- Modify: `frontend/src/components/workbench/SideBar.tsx` (`IntelView`, imports ~11 + ~145)
- Modify: `frontend/src/App.tsx` (`commands` ~91-99)
- Delete: `frontend/src/components/panels/StructureMapPanel.tsx`

**Interfaces:**
- Consumes: `openFile({ repoId, path: "::arch-map", name: "Architecture Map", kind: "graph" })`.

- [ ] **Step 1: Replace the Structure Map section with a launcher in `IntelView`**

In `SideBar.tsx`, remove the `import StructureMapPanel …` line and add near the other workbench imports:

```ts
import { useWorkbench } from "../../context/WorkbenchContext";
```

Replace `<Section title="Structure Map" defaultOpen><StructureMapPanel /></Section>` with a launcher (place at the top of `IntelView`'s scroll body):

```tsx
        <MapLauncher />
```

And add the component below `IntelView`:

```tsx
function MapLauncher() {
  const { openFile } = useWorkbench();
  const { activeId } = useRepo();
  return (
    <div style={{ padding: "8px 12px", borderBottom: `1px solid ${t.border}` }}>
      <button
        disabled={!activeId}
        onClick={() => activeId && openFile({ repoId: activeId, path: "::arch-map", name: "Architecture Map", kind: "graph" })}
        style={{ width: "100%", background: t.bgElev, color: t.text, border: `1px solid ${t.border}`,
          borderRadius: 6, padding: "8px 10px", fontSize: 12, fontFamily: t.sans, cursor: activeId ? "pointer" : "default", textAlign: "left" }}
      >
        ◈ Open Architecture Map ⬲
      </button>
    </div>
  );
}
```

Confirm `useRepo` is imported in `SideBar.tsx` (it is used elsewhere); if not, add `import { useRepo } from "../../context/RepoContext";`.

- [ ] **Step 2: Add the command-palette entry in `App.tsx`**

In the `commands` array (after the "Imperium Intelligence" entry), add:

```tsx
    { label: "View: Architecture Map", run: () => { if (activeId) openFile({ repoId: activeId, path: "::arch-map", name: "Architecture Map", kind: "graph" }); } },
```

`openFile` is already destructured from `useWorkbench()` at `App.tsx:80`; ensure `openFile` is in the `commands` `useMemo` dependency array alongside `activeId`.

- [ ] **Step 3: Delete the old panel**

```bash
git rm frontend/src/components/panels/StructureMapPanel.tsx
```

- [ ] **Step 4: Typecheck + build**

Run: `cd frontend && npx tsc -b && npm run build`
Expected: exit 0, build succeeds (no dangling `StructureMapPanel` import).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/SideBar.tsx frontend/src/App.tsx
git commit -m "feat(ui): launch Architecture Map from Intel panel + command palette; retire StructureMapPanel"
git push origin main
```

---

### Task 6: Final verification

- [ ] **Step 1: Backend suite**

Run: `cd backend && source .venv/bin/activate && python -m pytest -q`
Expected: all pass.

- [ ] **Step 2: Frontend typecheck + build**

Run: `cd frontend && npx tsc -b && npm run build`
Expected: exit 0, build succeeds.

- [ ] **Step 3: Confirm no lingering references**

Run: `grep -rn "StructureMapPanel" frontend/src || echo CLEAN`
Expected: `CLEAN`.
