// Primary sidebar — renders the view chosen in the activity bar.
import { useEffect, useMemo, useState } from "react";
import { api, type FileNode } from "../../api/client";
import { useRepo } from "../../context/RepoContext";
import { useWorkbench } from "../../context/WorkbenchContext";
import { useContextMenu } from "../../context/ContextMenuContext";
import { fileIcon } from "../../lib/fileIcons";
import { t } from "../../theme";
import { Btn } from "../ui";
import Explorer from "./Explorer";
import { AgentGraphMini } from "./AgentGraph";

import FindingsPanel from "../panels/FindingsPanel";
import RunEventsPanel from "../panels/RunEventsPanel";
import BusinessRulesPanel from "../panels/BusinessRulesPanel";
import TimelinePanel from "../panels/TimelinePanel";
import DecisionLogPanel from "../panels/DecisionLogPanel";
import ComprehensionPanel from "../panels/ComprehensionPanel";
import ClarificationsPanel from "../panels/ClarificationsPanel";
import PrioritiesPanel from "../panels/PrioritiesPanel";
import GateAPanel from "../panels/GateAPanel";
import ChangeReviewPanel from "../panels/ChangeReviewPanel";
import ProjectsPanel from "../panels/ProjectsPanel";

const header: React.CSSProperties = {
  padding: "8px 12px", fontSize: 11, fontWeight: 700, letterSpacing: 0.6,
  color: t.textDim, textTransform: "uppercase",
};

export default function SideBar() {
  const { view } = useWorkbench();
  return (
    <div style={{ width: "100%", height: "100%", background: t.bgPanel,
      display: "flex", flexDirection: "column", minHeight: 0, minWidth: 0 }}>
      {view === "projects" && <ProjectsPanel />}
      {view === "explorer" && (
        <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
          <OpenEditors />
          <div style={{ flex: 1, minHeight: 0 }}><Explorer /></div>
        </div>
      )}
      {view === "search" && <SearchView />}
      {view === "scm" && <SinglePanel title="Source Control"><ChangeReviewPanel /></SinglePanel>}
      {view === "run" && <RunView />}
      {view === "intel" && <IntelView />}
    </div>
  );
}

// ---- Open Editors: the currently-open tabs, VS Code style --------------------
function OpenEditors() {
  const { editors, activePath, setActivePath, closeFile, closeAll } = useWorkbench();
  const menu = useContextMenu();
  const [open, setOpen] = useState(true);
  if (editors.length === 0) return null;

  return (
    <div style={{ borderBottom: `1px solid ${t.border}`, flexShrink: 0 }}>
      <div onClick={() => setOpen((o) => !o)}
        style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", cursor: "pointer",
          fontSize: 11, fontWeight: 700, letterSpacing: 0.5, textTransform: "uppercase", color: t.text }}>
        <span style={{ fontSize: 9, color: t.textDim }}>{open ? "▼" : "▶"}</span>
        Open Editors
        <span style={{ color: t.textDim, fontWeight: 400 }}>{editors.length}</span>
        <span style={{ flex: 1 }} />
        <span title="Close All" onClick={(e) => { e.stopPropagation(); closeAll(); }}
          style={{ color: t.textDim, fontSize: 13 }}>⊗</span>
      </div>
      {open && (
        <div style={{ maxHeight: 160, overflow: "auto", paddingBottom: 4 }}>
          {editors.map((e) => {
            const sel = e.path === activePath;
            return (
              <div key={e.path} onClick={() => setActivePath(e.path)} title={e.path}
                onContextMenu={(ev) => menu.open(ev, [
                  { label: "Close", onClick: () => closeFile(e.path) },
                  { label: "Close All", onClick: closeAll },
                  { separator: true },
                  { label: "Copy Path", onClick: () => navigator.clipboard?.writeText(e.path) },
                ])}
                style={{ display: "flex", alignItems: "center", gap: 6, padding: "3px 12px 3px 22px",
                  fontSize: 13, cursor: "pointer", whiteSpace: "nowrap", overflow: "hidden",
                  color: sel ? t.text : t.textDim, background: sel ? t.bgHover : "transparent" }}
                onMouseEnter={(ev) => { if (!sel) ev.currentTarget.style.background = "#ffffff08"; }}
                onMouseLeave={(ev) => { if (!sel) ev.currentTarget.style.background = "transparent"; }}>
                <span onClick={(ev) => { ev.stopPropagation(); closeFile(e.path); }}
                  style={{ color: t.textDim, fontSize: 13, width: 12 }}>×</span>
                <span>{fileIcon(e.name)}</span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{e.name}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SinglePanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={header}>{title}</div>
      <div style={{ flex: 1, minHeight: 0 }}>{children}</div>
    </div>
  );
}

// ---- Search: fuzzy filename search across the workspace tree -----------------
function flatten(nodes: FileNode[], acc: FileNode[] = []): FileNode[] {
  for (const n of nodes) {
    if (n.type === "file") acc.push(n);
    else if (n.children) flatten(n.children, acc);
  }
  return acc;
}

function SearchView() {
  const { activeId } = useRepo();
  const { openFile } = useWorkbench();
  const [files, setFiles] = useState<FileNode[]>([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!activeId) return;
    api.fileTree(activeId).then((r) => setFiles(flatten(r.tree))).catch(() => setFiles([]));
  }, [activeId]);

  const results = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return [];
    return files.filter((f) => f.path.toLowerCase().includes(term)).slice(0, 200);
  }, [q, files]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={header}>Search</div>
      <div style={{ padding: "0 12px 8px" }}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search files by name…"
          style={{ width: "100%", boxSizing: "border-box", background: t.bg, color: t.text,
            border: `1px solid ${t.border}`, borderRadius: 5, padding: "6px 8px", fontSize: 13, outline: "none" }} />
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        {q && <div style={{ padding: "2px 12px", fontSize: 11, color: t.textDim }}>{results.length} result(s)</div>}
        {results.map((f) => (
          <div key={f.path} onClick={() => activeId && openFile({ repoId: activeId, path: f.path, name: f.name })}
            style={{ padding: "3px 12px", fontSize: 13, cursor: "pointer", color: t.textDim, whiteSpace: "nowrap",
              overflow: "hidden", textOverflow: "ellipsis" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#ffffff08")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
            <span style={{ marginRight: 6 }}>{fileIcon(f.name)}</span>{f.name}
            <span style={{ color: "#5a626c", marginLeft: 6, fontSize: 11 }}>{f.path}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Run & pipeline ----------------------------------------------------------
function RunView() {
  const { activeId } = useRepo();
  const { runId, setRunId } = useRepo();
  const { openFile } = useWorkbench();
  const start = async () => {
    if (!activeId) return;
    const r = await api.startRun(activeId);
    setRunId(r.run_id);
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={header}>Run &amp; Pipeline</div>
      <div style={{ padding: "0 12px 10px", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Btn kind="green" onClick={start} disabled={!activeId}>▶ Start Run</Btn>
        <button
          disabled={!runId}
          onClick={() => runId && activeId && openFile({ repoId: activeId, path: "::agent-graph", name: "Agent Graph", kind: "agent-graph" })}
          style={{ background: t.bgElev, color: runId ? t.text : t.textDim, border: `1px solid ${t.border}`,
            borderRadius: 6, padding: "5px 8px", fontSize: 11, fontFamily: t.sans, cursor: runId ? "pointer" : "default" }}
        >⧉ Open Agent Graph</button>
        {runId && <span style={{ fontSize: 11, color: t.textDim, fontFamily: t.mono }}>run {runId.slice(0, 8)}</span>}
      </div>
      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <Section title="Agent Graph" defaultOpen><AgentGraphMini runId={runId} /></Section>
        <Section title="Activity" defaultOpen><RunEventsPanel /></Section>
        <Section title="Priorities"><PrioritiesPanel /></Section>
        <Section title="Gate A"><GateAPanel /></Section>
      </div>
    </div>
  );
}

// ---- Imperium Intelligence: accordion of analysis panels ---------------------
function Section({ title, defaultOpen, children }: { title: string; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div style={{ borderBottom: `1px solid ${t.border}` }}>
      <div onClick={() => setOpen((o) => !o)}
        style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", cursor: "pointer",
          fontSize: 11, fontWeight: 700, letterSpacing: 0.5, textTransform: "uppercase", color: t.text }}>
        <span style={{ fontSize: 9, color: t.textDim }}>{open ? "▼" : "▶"}</span>{title}
      </div>
      {open && <div style={{ height: 280 }}>{children}</div>}
    </div>
  );
}

function MapLauncher() {
  const { openFile } = useWorkbench();
  const { activeId } = useRepo();
  const btn: React.CSSProperties = {
    flex: 1, background: t.bgElev, color: t.text, border: `1px solid ${t.border}`,
    borderRadius: 6, padding: "8px 10px", fontSize: 12, fontFamily: t.sans,
    cursor: activeId ? "pointer" : "default", textAlign: "left",
  };
  return (
    <div style={{ padding: "8px 12px", borderBottom: `1px solid ${t.border}`, display: "flex", gap: 6 }}>
      <button
        disabled={!activeId}
        onClick={() => activeId && openFile({ repoId: activeId, path: "::module-map", name: "Module Map", kind: "module-map" })}
        style={btn}
        title="Pages / components and how they connect"
      >▧ Module Map</button>
      <button
        disabled={!activeId}
        onClick={() => activeId && openFile({ repoId: activeId, path: "::api-map", name: "API Map", kind: "api-map" })}
        style={btn}
        title="Endpoint call arrows"
      >◈ API Map</button>
    </div>
  );
}

function IntelView() {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={header}>Imperium Intelligence</div>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <MapLauncher />
        <Section title="Findings"><FindingsPanel /></Section>
        <Section title="Business Rules"><BusinessRulesPanel /></Section>
        <Section title="Timeline"><TimelinePanel /></Section>
        <Section title="Decision Log"><DecisionLogPanel /></Section>
        <Section title="Comprehension"><ComprehensionPanel /></Section>
        <Section title="Clarifications"><ClarificationsPanel /></Section>
      </div>
    </div>
  );
}
