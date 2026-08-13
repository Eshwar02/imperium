# Project Management UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Imperium IDE workbench a discoverable way to add a project by git URL and switch the active project, from a dedicated Projects activity-bar view and the title bar / command palette.

**Architecture:** A shared `useProjectActions` hook wraps the existing `RepoContext` (single source of truth). A new `ProjectsPanel` (refit from the orphaned `RepoRail`) is rendered as a new `"projects"` activity-bar view. The title bar already has a repo `<select>` switcher; we add an "Add Project…" affordance that routes to the Projects view, plus command-palette entries for add + switch.

**Tech Stack:** React 18 + TypeScript (strict), Vite. No test runner is configured (`npm run build` = `tsc -b && vite build`); verification per task is type-check/build + manual smoke.

## Global Constraints

- No backend changes. Use existing `api.ingest(repo_url, ref="HEAD")`, `api.listRepos()`.
- `RepoContext` stays the single global store for `repos` / `activeId`; do not add a second store.
- Match existing style: inline styles from `theme` (`t`), components from `../ui` (`Btn`, `Badge`, `Empty`, `Row`), no new dependencies.
- Repo display name derives from `repo.url?.split("/").pop() ?? repo.id`.
- Verification command for every task: `cd frontend && npm run build` must pass with zero TS errors.
- Commit style: small granular commits, done serially (never by subagents). No Claude co-author trailer. Push to `main`.

---

### Task 1: Shared `useProjectActions` hook + `"projects"` activity view type

**Files:**
- Modify: `frontend/src/context/RepoContext.tsx` (append hook)
- Modify: `frontend/src/context/WorkbenchContext.tsx:5` (extend `ActivityView`)

**Interfaces:**
- Consumes: `useRepo()` → `{ repos, activeId, setActiveId, reloadRepos }`; `api.ingest`.
- Produces:
  - `useProjectActions(): { repos: Repo[]; activeId: string | null; setActiveId: (id: string) => void; ingest: (url: string) => Promise<void>; ingesting: boolean; error: string | null }`
  - `ActivityView` now includes `"projects"`.

- [ ] **Step 1: Extend the `ActivityView` union**

In `frontend/src/context/WorkbenchContext.tsx`, line 5, change:

```ts
export type ActivityView = "explorer" | "search" | "scm" | "run" | "intel";
```

to:

```ts
export type ActivityView = "projects" | "explorer" | "search" | "scm" | "run" | "intel";
```

- [ ] **Step 2: Append the `useProjectActions` hook to `RepoContext.tsx`**

At the end of `frontend/src/context/RepoContext.tsx`, add:

```tsx
// eslint-disable-next-line react-refresh/only-export-components
export function useProjectActions() {
  const { repos, activeId, setActiveId, reloadRepos } = useRepo();
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ingest = async (url: string) => {
    const trimmed = url.trim();
    if (!trimmed || ingesting) return;
    setIngesting(true);
    setError(null);
    try {
      const { repository_id } = await api.ingest(trimmed);
      await reloadRepos();
      setActiveId(repository_id);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setIngesting(false);
    }
  };

  return { repos, activeId, setActiveId, ingest, ingesting, error };
}
```

`useState` and `api` are already imported at the top of the file; no new imports needed.

- [ ] **Step 3: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS (zero TS errors). The hook is unused so far — that is fine; it is exported.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/context/RepoContext.tsx frontend/src/context/WorkbenchContext.tsx
git commit -m "feat(ui): useProjectActions hook + projects activity view type"
```

---

### Task 2: Projects activity-bar view (`ProjectsPanel`), wired into ActivityBar + SideBar

**Files:**
- Create: `frontend/src/components/panels/ProjectsPanel.tsx`
- Modify: `frontend/src/components/workbench/ActivityBar.tsx:6-12` (add item)
- Modify: `frontend/src/components/workbench/SideBar.tsx:26-38` (render view)
- Delete: `frontend/src/components/panels/RepoRail.tsx` (now superseded)

**Interfaces:**
- Consumes: `useProjectActions()` from Task 1.
- Produces: `ProjectsPanel` default export; activity view `"projects"` is now reachable.

- [ ] **Step 1: Create `ProjectsPanel.tsx`**

Create `frontend/src/components/panels/ProjectsPanel.tsx`:

```tsx
// Projects — add a repository by git URL and switch the active one.
// The single "add / open project" surface in the workbench sidebar.
import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { t } from "../../theme";
import { Empty, Badge, Btn, Row } from "../ui";
import { useProjectActions } from "../../context/RepoContext";

export interface ProjectsPanelHandle { focusInput: () => void }

const header: React.CSSProperties = {
  padding: "8px 12px", fontSize: 11, fontWeight: 700, letterSpacing: 0.6,
  color: t.textDim, textTransform: "uppercase",
};

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ borderBottom: `1px solid ${t.border}`, padding: "10px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
      <span style={{ fontSize: 11, letterSpacing: 0.6, textTransform: "uppercase", color: t.textDim, fontWeight: 700 }}>{label}</span>
      {children}
    </div>
  );
}

const ProjectsPanel = forwardRef<ProjectsPanelHandle>(function ProjectsPanel(_props, ref) {
  const { repos, activeId, setActiveId, ingest, ingesting, error } = useProjectActions();
  const [url, setUrl] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({ focusInput: () => inputRef.current?.focus() }), []);

  async function onAdd() {
    if (!url.trim() || ingesting) return;
    await ingest(url);
    setUrl("");
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0, background: t.bgPanel, overflow: "auto" }}>
      <div style={header}>Projects</div>

      <Section label="Add Project">
        <input
          ref={inputRef}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void onAdd(); }}
          placeholder="git repository URL"
          disabled={ingesting}
          style={{
            fontSize: 12, fontFamily: t.mono, padding: "5px 8px", borderRadius: 5,
            border: `1px solid ${t.border}`, background: t.bg, color: t.text, outline: "none",
          }}
        />
        <Row>
          <Btn kind="primary" onClick={() => void onAdd()} disabled={ingesting || !url.trim()}>
            {ingesting ? "Adding…" : "+ Add"}
          </Btn>
          {ingesting && <span style={{ fontSize: 12, color: t.textDim }}>working…</span>}
        </Row>
        {error && <span style={{ fontSize: 12, color: t.red }}>{error}</span>}
      </Section>

      <Section label="Repositories">
        {repos.length === 0 ? (
          <Empty>No repositories — add one above.</Empty>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {repos.map((r) => {
              const active = r.id === activeId;
              const name = r.url?.split("/").pop() ?? r.id;
              return (
                <div
                  key={r.id}
                  onClick={() => setActiveId(r.id)}
                  style={{
                    cursor: "pointer", padding: "5px 6px", borderRadius: 4,
                    background: active ? t.bgHover : "transparent",
                    borderLeft: `2px solid ${active ? t.accent : "transparent"}`,
                    display: "flex", flexDirection: "column", gap: 4,
                  }}
                >
                  <span style={{ fontSize: 12, fontFamily: t.mono, color: t.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {name}
                  </span>
                  {r.languages.length > 0 && (
                    <Row style={{ flexWrap: "wrap", gap: 4 }}>
                      {r.languages.map((l) => <Badge key={l}>{l}</Badge>)}
                    </Row>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Section>
    </div>
  );
});

export default ProjectsPanel;
```

Note: confirm `t.accent` exists in `frontend/src/theme.ts` (it is used by `RepoRail.tsx:158`). If the `Row` component does not accept a `style` prop, check its signature in `frontend/src/components/ui.tsx` and drop the `style` prop — `RepoRail.tsx:166` already passes `style` to `Row`, so it is supported.

- [ ] **Step 2: Add the activity-bar item**

In `frontend/src/components/workbench/ActivityBar.tsx`, change the `ITEMS` array (lines 6-12) to put Projects first:

```tsx
const ITEMS: { id: ActivityView; icon: string; label: string }[] = [
  { id: "projects", icon: "🗂", label: "Projects" },
  { id: "explorer", icon: "🗎", label: "Explorer" },
  { id: "search", icon: "🔍", label: "Search" },
  { id: "scm", icon: "⑃", label: "Source Control" },
  { id: "run", icon: "▷", label: "Run & Pipeline" },
  { id: "intel", icon: "◈", label: "Imperium Intelligence" },
];
```

- [ ] **Step 3: Render the view in `SideBar`, forwarding a ref**

In `frontend/src/components/workbench/SideBar.tsx`:

a) Add the import near the other panel imports (after line 9):

```tsx
import ProjectsPanel from "../panels/ProjectsPanel";
```

b) Replace the `SideBar` component (lines 26-38) with a version that renders the projects view:

```tsx
export default function SideBar() {
  const { view } = useWorkbench();
  return (
    <div style={{ width: 300, background: t.bgPanel, borderRight: `1px solid ${t.border}`,
      display: "flex", flexDirection: "column", minHeight: 0, flexShrink: 0 }}>
      {view === "projects" && <ProjectsPanel />}
      {view === "explorer" && <Explorer />}
      {view === "search" && <SearchView />}
      {view === "scm" && <SinglePanel title="Source Control"><ChangeReviewPanel /></SinglePanel>}
      {view === "run" && <RunView />}
      {view === "intel" && <IntelView />}
    </div>
  );
}
```

(The `focusInput` ref is exercised in Task 3 via the command palette / title bar; rendering `<ProjectsPanel />` without a ref here is valid because the ref prop is optional on a `forwardRef` component.)

- [ ] **Step 4: Delete the orphaned `RepoRail`**

Run: `git rm frontend/src/components/panels/RepoRail.tsx`
First confirm nothing imports it:
Run: `grep -rn "RepoRail" frontend/src` — expected: no matches after deletion (should already be none, since it is orphaned).

- [ ] **Step 5: Type-check / build**

Run: `cd frontend && npm run build`
Expected: PASS (zero TS errors).

- [ ] **Step 6: Manual smoke**

Run: `cd frontend && npm run dev`, open the app, sign in. Confirm: a Projects icon (🗂) appears at the top of the activity bar; clicking it shows the Add Project input + repositories list; pasting a git URL and clicking "+ Add" ingests and selects the repo; clicking a repo row switches the active project (Explorer updates).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/panels/ProjectsPanel.tsx frontend/src/components/workbench/ActivityBar.tsx frontend/src/components/workbench/SideBar.tsx
git rm frontend/src/components/panels/RepoRail.tsx
git commit -m "feat(ui): Projects activity-bar view to add/switch repositories; retire RepoRail"
```

---

### Task 3: Title-bar "Add Project…" affordance + command-palette entries

**Files:**
- Modify: `frontend/src/components/workbench/TitleBar.tsx:55-80` (File menu entry)
- Modify: `frontend/src/App.tsx:91-101` (palette commands)

**Interfaces:**
- Consumes: `useWorkbench().setView`, `useRepo()` (`repos`, `setActiveId`) — both already imported in these files.
- Produces: no new exports; behavioural only.

- [ ] **Step 1: Add "Add Project…" to the title-bar File menu**

In `frontend/src/components/workbench/TitleBar.tsx`, in the `File` menu array (lines 56-61), add an entry that opens the Projects view. Replace:

```tsx
    File: [
      { label: "Command Palette…", action: onPalette },
      { label: "Open Explorer", action: () => setView("explorer") },
      { sep: true, label: "" },
      { label: "Sign out", action: signOut },
    ],
```

with:

```tsx
    File: [
      { label: "Add Project…", action: () => setView("projects") },
      { label: "Command Palette…", action: onPalette },
      { label: "Open Explorer", action: () => setView("explorer") },
      { sep: true, label: "" },
      { label: "Sign out", action: signOut },
    ],
```

`setView` is already destructured from `useWorkbench()` at line 45.

- [ ] **Step 2: Add palette entries for add + per-repo switch**

In `frontend/src/App.tsx`, the `CommandPalette` already destructures `activeId` and `setRunId` from `useRepo()` (line 79) and `setView`, `openFile` from `useWorkbench()` (line 80). Update line 79 to also pull `repos` and `setActiveId`:

```tsx
  const { repos, activeId, setActiveId, setRunId } = useRepo();
```

Then extend the `commands` array (lines 91-101). Replace it with:

```tsx
  const commands = useMemo(() => [
    { label: "Project: Add…", run: () => setView("projects") },
    ...repos.map((r) => ({
      label: `Project: Switch to ${r.url?.split("/").pop() ?? r.id}`,
      run: () => setActiveId(r.id),
    })),
    { label: "▶ Start Pipeline Run", run: async () => { if (activeId) { const r = await api.startRun(activeId); setRunId(r.run_id); setView("run"); } } },
    { label: "View: Explorer", run: () => setView("explorer") },
    { label: "View: Search", run: () => setView("search") },
    { label: "View: Source Control", run: () => setView("scm") },
    { label: "View: Imperium Intelligence", run: () => setView("intel") },
    { label: "View: Architecture Map", run: () => { if (activeId) openFile({ repoId: activeId, path: "::arch-map", name: "Architecture Map", kind: "graph" }); } },
    { label: "Toggle Primary Sidebar", run: onToggleSidebar },
    { label: "Toggle Panel", run: onTogglePanel },
    { label: "Toggle Chat", run: onToggleChat },
  ], [repos, activeId, setActiveId, setRunId, setView, openFile, onToggleSidebar, onTogglePanel, onToggleChat]);
```

- [ ] **Step 3: Type-check / build**

Run: `cd frontend && npm run build`
Expected: PASS (zero TS errors).

- [ ] **Step 4: Manual smoke**

In `npm run dev`: open the File menu → "Add Project…" switches the sidebar to the Projects view. Open the command palette (Ctrl+Shift+P) → "Project: Add…" opens the Projects view; "Project: Switch to <name>" entries appear (one per repo) and switch the active project.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/TitleBar.tsx frontend/src/App.tsx
git commit -m "feat(ui): Add Project entry in title-bar menu + command palette add/switch"
```

---

## Self-Review

**Spec coverage:**
- Shared `useProjectActions` hook → Task 1. ✓
- Projects activity-bar view (refit RepoRail, ingest + list, delete RepoRail) → Task 2. ✓
- Title-bar add affordance → Task 3 Step 1 (switcher already exists as a `<select>`; spec's "add a switcher" is satisfied by the existing control, so only the "Add Project…" affordance is added — noted in plan header). ✓
- Command-palette add + switch entries → Task 3 Step 2. ✓
- Out of scope (delete project) → not built. ✓
- No backend changes → honored. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows full code. ✓

**Type consistency:** `useProjectActions` return shape defined in Task 1 is consumed verbatim in Task 2 (`repos, activeId, setActiveId, ingest, ingesting, error`). `ActivityView` value `"projects"` defined in Task 1, used in Tasks 2 (ActivityBar/SideBar) and 3 (`setView("projects")`). ✓
