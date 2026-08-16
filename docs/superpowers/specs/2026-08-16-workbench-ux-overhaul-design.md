# Workbench UX Overhaul — design

**Date:** 2026-08-16
**Status:** Approved, in implementation

## Problem

The Imperium IDE workbench is functional but has visibility and usability gaps:

1. **No agent transparency.** The backend already emits a live agent graph
   (`core/agent_graph.py`, served at `GET /api/runs/{id}/graph`) and an event
   stream, but nothing in the frontend consumes the graph, and `RunEventsPanel`
   only dumps raw JSON and is not even wired into the Run view.
2. **No way to add or switch a project in the running app.** `RepoRail.tsx`
   (git-URL ingest + repo picker) is orphaned — rendered nowhere.
3. **Fixed panel sizes.** The left sidebar (300px), right chat (340px), and
   bottom panel (240px) are hardcoded; they crowd the editor and can't be
   resized like a real IDE.
4. **Cluttered architecture graph.** `ArchitectureMap` merges the `api` and
   `arch` layers into one graph, so API arrows swamp the module/page structure.

## Goal

Bring the workbench to IDE-grade usability (VS Code-style): transparent live
runs, discoverable project management, resizable regions, and two focused graph
views — with a real frontend test harness backing the new work.

## Build order

1. Live Agent Graph (transparency)
2. Projects: add-by-git-URL + switch
3. Resizable panels
4. Graph split into two tabs
5. Usability + testing pass (cross-cutting, lands alongside each feature)

Each feature is pushed to `main` in small, granular commits.

## 1. Live Agent Graph

**Backend:** no changes. `GET /api/runs/{run_id}/graph` returns
`{run_id, status, stage, nodes, edges}` where each node has
`status ∈ {idle, active, done, awaiting, failed}` and `type ∈ {run, stage, gate, agent}`.

**Frontend:**
- New client method `api.runGraph(runId)`.
- New `AgentGraph.tsx` (React Flow) rendering Orchestrator → stages → sub-agents,
  colored/iconed by status. Polls every ~1.5s while the run is live; stops on
  `complete`/`failed`/`cancelled`.
- Opened as a full-screen editor tab (`kind: "agent-graph"`) from the Intel view
  and command palette, mirroring how the Architecture Map opens.
- A **compact** `AgentGraph` also renders inside the Run view (`SideBar` →
  `RunView`), above a **readable activity feed** — `RunEventsPanel` reworked to
  format events into human lines (e.g. `Structure agent finished — 4 findings`)
  instead of raw JSON, and finally wired into the Run view.

**Node status → style** is a pure function (`agentNodeStyle(status)`), unit-tested
independently of React Flow.

## 2. Projects: add + switch

Implements the previously approved
`2026-08-13-project-management-ui-design.md` unchanged:

- `useProjectActions` hook (co-located with `RepoContext`) = single source of
  truth: `ingest(url)` → `api.ingest` → `reloadRepos` → `setActiveId`; exposes
  `ingesting` / `error` and re-exposes `repos` / `activeId` / `setActiveId`.
- `ProjectsPanel.tsx` (refit from `RepoRail`, ingest + repo list only) as a top
  **🗂 Projects** activity-bar view.
- `TitleBar` project switcher dropdown with a trailing **+ Add Project…** entry.
- Command palette: `Project: Add…` and `Project: Switch to <name>` per repo.
- Delete the dead `RepoRail.tsx`.

No backend changes. Delete-project is out of scope (no endpoint).

## 3. Resizable panels

- Reusable `<Resizer />` component: a thin draggable handle that reports a
  pixel delta; the parent clamps to `[min, max]` and stores the size.
- Applied to the left sidebar (horizontal), right chat (horizontal), and bottom
  panel (vertical).
- Sizes persist to `localStorage` (`imperium.layout.*`) and restore on load.
- Sensible clamps so no region collapses or eats the editor:
  sidebar `[180, 560]`, chat `[240, 640]`, panel `[120, 480]`.
- Size clamping is a pure helper (`clampSize`), unit-tested.

## 4. Graph split → two tabs

- Extract the shared React Flow canvas from `ArchitectureMap` into
  `GraphCanvas.tsx` taking a `layer` prop, keeping layout + click-to-open logic
  in one place.
- **Module Map** tab (`kind: "module-map"`) — `arch` layer only (pages /
  components and their links).
- **API Map** tab (`kind: "api-map"`) — `api` layer only (endpoint call arrows).
- Both launchable from the Intel view and command palette. `ArchitectureMap`
  becomes a thin wrapper (or is replaced by the two tabs).

## 5. Usability + testing

**Usability:** every new surface gets consistent headers and empty / loading /
error states; buttons keyboard-reachable; min-sizes prevent collapse; visuals
match the existing VS Code-style shell (`theme.ts`, `components/ui.tsx`).

**Testing:** stand up **Vitest + React Testing Library** (none exists today).
Cover new and changed units:
- `useProjectActions` (ingest success/error, active-id follow-through)
- `agentNodeStyle` status→style mapping
- `clampSize` resizer clamping
- graph layer selection (Module vs API requests the right layer)
- readable-feed event formatter
- smoke render tests for each panel touched (Projects, AgentGraph, Run view,
  the two map tabs)

Scope note: new/changed components are tested thoroughly; pre-existing untouched
panels are not retro-tested here (separate, larger effort).

## Data flow

```
Run:   startRun ─► runId ─► api.runGraph(poll) ─► AgentGraph (live nodes)
                         └─► api.runEvents(SSE) ─► readable feed
Project: ingest(url)/switch ─► useProjectActions ─► RepoContext (repos, activeId)
                                                     └─► every panel re-renders
Graph: Module/API tab ─► api.graph(id, "arch"|"api") ─► GraphCanvas
Layout: drag ─► clampSize ─► localStorage ─► region width/height
```

## Verification

- `tsc` / production build passes (strict TS).
- `vitest run` green for all new/changed units.
- Manual smoke: start a run and watch nodes light up; add a repo by URL and see
  it become active in both surfaces; drag each region and reload to confirm
  persistence; open Module Map and API Map and confirm each shows only its layer.
