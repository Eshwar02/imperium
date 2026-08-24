// Workbench UI state — the moving parts of the VS Code-style shell:
// which activity view is active, which editors are open, and what's visible.
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export type ActivityView = "explorer" | "search" | "scm" | "run" | "intel" | "projects";
export type PanelTab = "problems" | "output" | "terminal" | "runs";

export interface OpenEditor {
  repoId: string;
  // repo-relative path, or a synthetic key like "::module-map" / "::api-map" / "::agent-graph"
  path: string;
  name: string;
  kind?: "file" | "module-map" | "api-map" | "agent-graph";
}

interface WorkbenchCtx {
  view: ActivityView;
  setView: (v: ActivityView) => void;

  sidebarOpen: boolean;
  toggleSidebar: () => void;

  chatOpen: boolean;
  toggleChat: () => void;

  panelOpen: boolean;
  togglePanel: () => void;
  panelTab: PanelTab;
  setPanelTab: (t: PanelTab) => void;

  editors: OpenEditor[];
  activePath: string | null;
  openFile: (e: OpenEditor) => void;
  closeFile: (path: string) => void;
  closeOthers: (path: string) => void;
  closeAll: () => void;
  setActivePath: (path: string) => void;
}

const Ctx = createContext<WorkbenchCtx | null>(null);

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  const [view, setViewRaw] = useState<ActivityView>("explorer");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatOpen, setChatOpen] = useState(true);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelTab, setPanelTab] = useState<PanelTab>("problems");
  const [editors, setEditors] = useState<OpenEditor[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);

  // Clicking the already-active activity icon collapses the sidebar (VS Code behaviour).
  const setView = useCallback((v: ActivityView) => {
    setViewRaw((cur) => {
      if (cur === v) setSidebarOpen((o) => !o);
      else setSidebarOpen(true);
      return v;
    });
  }, []);

  const openFile = useCallback((e: OpenEditor) => {
    setEditors((list) => (list.some((x) => x.path === e.path) ? list : [...list, e]));
    setActivePath(e.path);
  }, []);

  const closeFile = useCallback((path: string) => {
    setEditors((list) => {
      const idx = list.findIndex((x) => x.path === path);
      const next = list.filter((x) => x.path !== path);
      setActivePath((cur) => {
        if (cur !== path) return cur;
        if (next.length === 0) return null;
        return (next[idx] ?? next[idx - 1] ?? next[0]).path;
      });
      return next;
    });
  }, []);

  const closeOthers = useCallback((path: string) => {
    setEditors((list) => list.filter((x) => x.path === path));
    setActivePath(path);
  }, []);

  const closeAll = useCallback(() => {
    setEditors([]);
    setActivePath(null);
  }, []);

  return (
    <Ctx.Provider
      value={{
        view, setView,
        sidebarOpen, toggleSidebar: () => setSidebarOpen((o) => !o),
        chatOpen, toggleChat: () => setChatOpen((o) => !o),
        panelOpen, togglePanel: () => setPanelOpen((o) => !o),
        panelTab, setPanelTab,
        editors, activePath, openFile, closeFile, closeOthers, closeAll, setActivePath,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useWorkbench() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useWorkbench must be inside WorkbenchProvider");
  return c;
}
