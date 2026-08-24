// Imperium IDE — VS Code-style workbench: title/menu bar, activity bar, sidebar,
// editor group, bottom panel, right-hand chat, and status bar.
import { useEffect, useMemo, useState } from "react";
import { api, type FileNode } from "./api/client";
import { useRepo } from "./context/RepoContext";
import { useWorkbench } from "./context/WorkbenchContext";
import { fileIcon } from "./lib/fileIcons";
import { t } from "./theme";

import TitleBar from "./components/workbench/TitleBar";
import ActivityBar from "./components/workbench/ActivityBar";
import SideBar from "./components/workbench/SideBar";
import EditorArea from "./components/workbench/EditorArea";
import Panel from "./components/workbench/Panel";
import Resizer from "./components/workbench/Resizer";
import StatusBar from "./components/workbench/StatusBar";
import ChatPanel from "./components/panels/ChatPanel";
import { useResizable } from "./hooks";

export default function App() {
  const wb = useWorkbench();
  const { sidebarOpen, panelOpen, chatOpen, togglePanel, toggleSidebar, toggleChat } = wb;
  const [palette, setPalette] = useState<null | "cmd" | "file">(null);
  const [sidebarW, setSidebarW] = useResizable("sidebar", 300, 180, 560);
  const [chatW, setChatW] = useResizable("chat", 340, 240, 640);
  const [panelH, setPanelH] = useResizable("panel", 240, 120, 480);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.shiftKey && e.key.toLowerCase() === "p") { e.preventDefault(); setPalette("cmd"); }
      else if (mod && e.key.toLowerCase() === "p") { e.preventDefault(); setPalette("file"); }
      else if (mod && e.key.toLowerCase() === "b") { e.preventDefault(); toggleSidebar(); }
      else if (mod && (e.key === "`" || e.key.toLowerCase() === "j")) { e.preventDefault(); togglePanel(); }
      else if (e.key === "Escape") setPalette(null);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [toggleSidebar, togglePanel]);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column",
      background: t.bg, color: t.text, fontFamily: t.sans, overflow: "hidden" }}>
      <TitleBar onPalette={() => setPalette("cmd")} />

      <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
        <ActivityBar />
        {sidebarOpen && (
          <>
            <div style={{ width: sidebarW, flexShrink: 0, minWidth: 0, borderRight: `1px solid ${t.border}` }}>
              <SideBar />
            </div>
            <Resizer axis="x" size={sidebarW} min={180} max={560} onChange={setSidebarW} />
          </>
        )}

        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
          <div style={{ flex: 1, minHeight: 0 }}><EditorArea /></div>
          {panelOpen && (
            <>
              <Resizer axis="y" invert size={panelH} min={120} max={480} onChange={setPanelH} />
              <div style={{ height: panelH, flexShrink: 0 }}><Panel /></div>
            </>
          )}
        </div>

        {chatOpen && (
          <>
            <Resizer axis="x" invert size={chatW} min={240} max={640} onChange={setChatW} />
            <div style={{ width: chatW, flexShrink: 0, borderLeft: `1px solid ${t.border}`, minHeight: 0 }}>
              <ChatPanel />
            </div>
          </>
        )}
      </div>

      <StatusBar />

      {palette && (
        <CommandPalette mode={palette} onClose={() => setPalette(null)}
          onToggleSidebar={toggleSidebar} onTogglePanel={togglePanel} onToggleChat={toggleChat} />
      )}
    </div>
  );
}

function flatten(nodes: FileNode[], acc: FileNode[] = []): FileNode[] {
  for (const n of nodes) {
    if (n.type === "file") acc.push(n);
    else if (n.children) flatten(n.children, acc);
  }
  return acc;
}

function CommandPalette({ mode, onClose, onToggleSidebar, onTogglePanel, onToggleChat }: {
  mode: "cmd" | "file"; onClose: () => void;
  onToggleSidebar: () => void; onTogglePanel: () => void; onToggleChat: () => void;
}) {
  const { activeId, runId, setRunId, repos, setActiveId } = useRepo();
  const { setView, openFile } = useWorkbench();
  const [q, setQ] = useState(mode === "cmd" ? ">" : "");
  const [files, setFiles] = useState<FileNode[]>([]);

  useEffect(() => {
    if (!activeId) return;
    api.fileTree(activeId).then((r) => setFiles(flatten(r.tree))).catch(() => setFiles([]));
  }, [activeId]);

  const isCmd = q.startsWith(">");
  const [sel, setSel] = useState(0);

  const commands = useMemo(() => [
    { label: "▶ Start Pipeline Run", run: async () => { if (activeId) { const r = await api.startRun(activeId); setRunId(r.run_id); setView("run"); } } },
    { label: "View: Agent Graph (live run)", run: () => { if (activeId && runId) openFile({ repoId: activeId, path: "::agent-graph", name: "Agent Graph", kind: "agent-graph" }); else setView("run"); } },
    { label: "Project: Add…", run: () => setView("projects") },
    ...repos.map((r) => ({
      label: `Project: Switch to ${(r.url?.replace(/\.git$/, "").split("/").pop() ?? r.id)}`,
      run: () => setActiveId(r.id),
    })),
    { label: "View: Explorer", run: () => setView("explorer"), hint: "Ctrl+Shift+E" },
    { label: "View: Search", run: () => setView("search"), hint: "Ctrl+Shift+F" },
    { label: "View: Source Control", run: () => setView("scm") },
    { label: "View: Imperium Intelligence", run: () => setView("intel") },
    { label: "View: Module Map", run: () => { if (activeId) openFile({ repoId: activeId, path: "::module-map", name: "Module Map", kind: "module-map" }); } },
    { label: "View: API Map", run: () => { if (activeId) openFile({ repoId: activeId, path: "::api-map", name: "API Map", kind: "api-map" }); } },
    { label: "Toggle Primary Sidebar", run: onToggleSidebar, hint: "Ctrl+B" },
    { label: "Toggle Panel", run: onTogglePanel, hint: "Ctrl+J" },
    { label: "Toggle Chat", run: onToggleChat },
  ] as { label: string; run: () => void; hint?: string }[], [activeId, runId, repos, setActiveId, openFile]);

  const term = q.replace(/^>/, "").trim().toLowerCase();
  const cmdResults = commands.filter((c) => c.label.toLowerCase().includes(term));
  const fileResults = files.filter((f) => f.path.toLowerCase().includes(term)).slice(0, 100);
  const count = isCmd ? cmdResults.length : fileResults.length;

  // Keep the highlight in range whenever the result set changes.
  useEffect(() => { setSel(0); }, [q, count]);

  const runAt = (i: number) => {
    if (isCmd) { cmdResults[i]?.run(); onClose(); }
    else { const f = fileResults[i]; if (f && activeId) openFile({ repoId: activeId, path: f.path, name: f.name }); onClose(); }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, count - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); runAt(sel); }
  };

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "#0007",
      display: "flex", justifyContent: "center", paddingTop: 80, zIndex: 200 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 560, height: "fit-content", maxHeight: "70vh",
        background: t.bgElev, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden",
        boxShadow: "0 12px 48px #000b", display: "flex", flexDirection: "column" }}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKeyDown}
          placeholder={isCmd ? "Type a command…" : "Go to file…"}
          style={{ padding: "12px 14px", background: "transparent", border: "none",
            borderBottom: `1px solid ${t.border}`, color: t.text, fontSize: 14, outline: "none" }} />
        <div style={{ overflow: "auto" }}>
          {isCmd
            ? cmdResults.map((c, i) => (
                <div key={i} onClick={() => runAt(i)} onMouseEnter={() => setSel(i)}
                  style={{ ...itemStyle, background: i === sel ? t.bgHover : "transparent",
                    display: "flex", justifyContent: "space-between", gap: 16 }}>
                  <span>{c.label}</span>
                  {c.hint && <span style={{ color: t.textDim, fontSize: 11 }}>{c.hint}</span>}
                </div>
              ))
            : fileResults.map((f, i) => (
                <div key={f.path} onClick={() => runAt(i)} onMouseEnter={() => setSel(i)}
                  style={{ ...itemStyle, background: i === sel ? t.bgHover : "transparent" }}>
                  <span style={{ marginRight: 8 }}>{fileIcon(f.name)}</span>{f.name}
                  <span style={{ color: t.textDim, marginLeft: 8, fontSize: 12 }}>{f.path}</span>
                </div>
              ))}
          {count === 0 && <div style={{ ...itemStyle, color: t.textDim, fontStyle: "italic" }}>No matching results</div>}
        </div>
      </div>
    </div>
  );
}

const itemStyle: React.CSSProperties = { padding: "8px 14px", fontSize: 13, cursor: "pointer", color: t.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" };
