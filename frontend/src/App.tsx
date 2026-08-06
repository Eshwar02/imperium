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
import StatusBar from "./components/workbench/StatusBar";
import ChatPanel from "./components/panels/ChatPanel";

export default function App() {
  const wb = useWorkbench();
  const { sidebarOpen, panelOpen, chatOpen, togglePanel, toggleSidebar, toggleChat } = wb;
  const [palette, setPalette] = useState<null | "cmd" | "file">(null);

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
        {sidebarOpen && <SideBar />}

        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
          <div style={{ flex: 1, minHeight: 0 }}><EditorArea /></div>
          {panelOpen && <div style={{ height: 240, flexShrink: 0 }}><Panel /></div>}
        </div>

        {chatOpen && (
          <div style={{ width: 340, flexShrink: 0, borderLeft: `1px solid ${t.border}`, minHeight: 0 }}>
            <ChatPanel />
          </div>
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
  const { activeId, setRunId } = useRepo();
  const { setView, openFile } = useWorkbench();
  const [q, setQ] = useState(mode === "cmd" ? ">" : "");
  const [files, setFiles] = useState<FileNode[]>([]);

  useEffect(() => {
    if (!activeId) return;
    api.fileTree(activeId).then((r) => setFiles(flatten(r.tree))).catch(() => setFiles([]));
  }, [activeId]);

  const isCmd = q.startsWith(">");

  const commands = useMemo(() => [
    { label: "▶ Start Pipeline Run", run: async () => { if (activeId) { const r = await api.startRun(activeId); setRunId(r.run_id); setView("run"); } } },
    { label: "View: Explorer", run: () => setView("explorer") },
    { label: "View: Search", run: () => setView("search") },
    { label: "View: Source Control", run: () => setView("scm") },
    { label: "View: Imperium Intelligence", run: () => setView("intel") },
    { label: "Toggle Primary Sidebar", run: onToggleSidebar },
    { label: "Toggle Panel", run: onTogglePanel },
    { label: "Toggle Chat", run: onToggleChat },
  ], [activeId]);

  const term = q.replace(/^>/, "").trim().toLowerCase();
  const cmdResults = commands.filter((c) => c.label.toLowerCase().includes(term));
  const fileResults = files.filter((f) => f.path.toLowerCase().includes(term)).slice(0, 100);

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "#0007",
      display: "flex", justifyContent: "center", paddingTop: 80, zIndex: 200 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 560, height: "fit-content", maxHeight: "70vh",
        background: t.bgElev, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden",
        boxShadow: "0 12px 48px #000b", display: "flex", flexDirection: "column" }}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
          placeholder={isCmd ? "Type a command…" : "Go to file…"}
          style={{ padding: "12px 14px", background: "transparent", border: "none",
            borderBottom: `1px solid ${t.border}`, color: t.text, fontSize: 14, outline: "none" }} />
        <div style={{ overflow: "auto" }}>
          {isCmd
            ? cmdResults.map((c, i) => (
                <div key={i} onClick={() => { c.run(); onClose(); }} style={itemStyle}
                  onMouseEnter={(e) => (e.currentTarget.style.background = t.bgHover)}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  {c.label}
                </div>
              ))
            : fileResults.map((f) => (
                <div key={f.path} onClick={() => { if (activeId) openFile({ repoId: activeId, path: f.path, name: f.name }); onClose(); }}
                  style={itemStyle}
                  onMouseEnter={(e) => (e.currentTarget.style.background = t.bgHover)}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  <span style={{ marginRight: 8 }}>{fileIcon(f.name)}</span>{f.name}
                  <span style={{ color: t.textDim, marginLeft: 8, fontSize: 12 }}>{f.path}</span>
                </div>
              ))}
        </div>
      </div>
    </div>
  );
}

const itemStyle: React.CSSProperties = { padding: "8px 14px", fontSize: 13, cursor: "pointer", color: t.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" };
