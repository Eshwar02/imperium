# Project Management UI — design

**Date:** 2026-08-13
**Status:** Approved, pending implementation plan

## Problem

The Imperium IDE workbench (`App` → `ActivityBar` → `SideBar`) has no way to
**add a new project** or **switch the active project**. The activity bar only
offers Explorer / Search / Source Control / Run / Intelligence.

The ingest UI already exists in `frontend/src/components/panels/RepoRail.tsx`
(git-URL input → `POST /api/ingest`, plus a repo picker), but `RepoRail` is
**orphaned** — it is not rendered anywhere in the current workbench. So there is
no button to add or open a project in the running app.

Backend and shared state are already in place — no backend changes required:

- `api.ingest(repo_url, ref = "HEAD")` → `{ repository_id, languages }`
- `api.listRepos()` → `{ repositories: Repo[] }`
- `RepoContext`: `repos`, `activeId`, `setActiveId`, `reloadRepos`
- `Repo = { id, url, ref, languages, created_at }`

## Goal

Surface "add project" and "switch project" in two discoverable places that
share one source of truth:

1. A dedicated **Projects** activity-bar view.
2. A **title-bar switcher** plus **command-palette** entries.

## Scope

**In scope:** add a project by git URL (ingest); switch the active project.

**Out of scope:** removing/deleting a project — no backend endpoint exists
(only `DELETE /runs/{run_id}`). Would require a new backend route; not built now.

No automated frontend tests exist in the repo; verification is type-check/build
plus manual smoke. If a test runner is added later, cover `useProjectActions`.

## Components

### 1. `useProjectActions` hook (shared logic)

New hook (co-located with `RepoContext.tsx`) wrapping the existing context so
both surfaces stay in sync. Responsibilities:

- `ingest(url: string)`: call `api.ingest(url)`, then `reloadRepos()`, then
  `setActiveId(repository_id)`. Exposes `ingesting: boolean` and
  `error: string | null`.
- Re-expose `repos`, `activeId`, `setActiveId` from `RepoContext`.

This is the single source of truth. The Projects panel and the title-bar
switcher both call it; no duplicated ingest/switch logic.

### 2. Projects activity-bar view — `ProjectsPanel.tsx`

Refit from the orphaned `RepoRail`, trimmed to **ingest + repo list only**.
The Run and Hierarchy sections in `RepoRail` are dropped: Run is already the
Run & Pipeline view, and Hierarchy belongs to Intelligence — keeping them here
would duplicate UI.

- `ActivityView` type (`WorkbenchContext`) gains `"projects"`.
- `ActivityBar` `ITEMS` gains `{ id: "projects", icon: "🗂", label: "Projects" }`
  at the **top** of the list.
- `SideBar` renders `<ProjectsPanel />` when `view === "projects"`.
- Panel contents:
  - Git-URL input + **Add** button → `useProjectActions().ingest`. Shows a
    spinner while `ingesting` and an inline error on failure (existing pattern).
  - Repo list: each row shows the repo name (derived from `url`, falling back to
    `id`) and language badges. Clicking a row calls `setActiveId`. The active
    repo's row is highlighted (accent left-border, as `RepoRail` already does).
- Delete the now-dead `RepoRail.tsx`.

### 3. Title-bar switcher + palette command

- `TitleBar`: render the active project's name as a compact dropdown button.
  Opening it lists all repos (click to `setActiveId`) with a trailing
  **"+ Add Project…"** entry that switches the sidebar to the Projects view and
  focuses its input — no separate modal.
- `App.tsx` command palette (`CommandPalette`): add
  - `"Project: Add…"` → switch to Projects view.
  - `"Project: Switch to <name>"` — one entry per repo, driven by `repos`,
    each calling `setActiveId`.

## Data flow

```
ingest(url) / switch ──► useProjectActions ──► RepoContext (activeId, repos)
                                                     │
                       every panel already reads ────┘  (re-renders on activeId)
```

No new global state; `RepoContext` remains the single store.

## Error handling

- Ingest errors: caught in `useProjectActions`, surfaced inline in the Projects
  panel. Same for the title-bar "+ Add Project…" path (routes into the panel).
- Switching is local state and cannot fail.

## Verification

- `tsc` / production build passes (strict TS).
- Manual smoke: add a repo by URL, confirm it appears and becomes active in both
  the Projects panel and the title-bar switcher; switch between repos from each
  surface and confirm Explorer/panels follow.
