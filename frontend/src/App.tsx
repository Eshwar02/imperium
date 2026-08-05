// Imperium IDE shell — docked, VS Code-style layout wiring every panel to the pipeline.
import { useEffect, useState } from "react";
import { useAuth } from "./context/AuthContext";
import { useRepo } from "./context/RepoContext";
import { api } from "./api/client";
import { t } from "./theme";
import { Btn } from "./components/ui";

import RepoRail from "./components/panels/RepoRail";
import StructureMapPanel from "./components/panels/StructureMapPanel";
import ChangeReviewPanel from "./components/panels/ChangeReviewPanel";
import FindingsPanel from "./components/panels/FindingsPanel";
import TimelinePanel from "./components/panels/TimelinePanel";
import PrioritiesPanel from "./components/panels/PrioritiesPanel";
import BusinessRulesPanel from "./components/panels/BusinessRulesPanel";
import ClarificationsPanel from "./components/panels/ClarificationsPanel";
import GateAPanel from "./components/panels/GateAPanel";
import DecisionLogPanel from "./components/panels/DecisionLogPanel";
import ChatPanel from "./components/panels/ChatPanel";
import RunEventsPanel from "./components/panels/RunEventsPanel";
import ComprehensionPanel from "./components/panels/ComprehensionPanel";
import StatusBar from "./components/panels/StatusBar";

type CenterTab = "map" | "changes" | "findings" | "timeline";
type BottomTab = "gatea" | "decisions" | "chat" | "runs" | "comprehension";

const CENTER: { id: CenterTab; label: string }[] = [
  { id: "map", label: "Structure Map" },
  { id: "changes", label: "Change Review" },
  { id: "findings", label: "Findings" },
  { id: "timeline", label: "Timeline" },
];
const BOTTOM: { id: BottomTab; label: string }[] = [
  { id: "gatea", label: "Gate A" },
  { id: "decisions", label: "Decision Log" },
  { id: "chat", label: "RKB Chat" },
  { id: "runs", label: "Run Events" },
  { id: "comprehension", label: "Comprehension" },
];

function TabBar<T extends string>({ tabs, active, onSelect }: {
  tabs: { id: T; label: string }[]; active: T; onSelect: (id: T) => void;
}) {
  return (
    <div style={{ display: "flex", background: t.bg, borderBottom: `1px solid ${t.border}`, flexShrink: 0 }}>
      {tabs.map((tab) => (
        <button key={tab.id} onClick={() => onSelect(tab.id)}
          style={{ padding: "7px 14px", fontSize: 12, fontFamily: t.sans, cursor: "pointer",
            background: active === tab.id ? t.bgPanel : "transparent",
            color: active === tab.id ? t.text : t.textDim, border: "none",
            borderBottom: active === tab.id ? `2px solid ${t.accent}` : "2px solid transparent" }}>
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const { user, signOut } = useAuth();
  const { repos, activeId, setActiveId, runId, setRunId } = useRepo();
  const [center, setCenter] = useState<CenterTab>("map");
  const [bottom, setBottom] = useState<BottomTab>("gatea");
  const [palette, setPalette] = useState(false);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); }
      if (e.key === "Escape") setPalette(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const startRun = async () => {
    if (!activeId) return;
    const r = await api.startRun(activeId);
    setRunId(r.run_id);
    setBottom("runs");
  };

  return (
    <div style={{
      height: "100vh", background: t.bg, color: t.text, fontFamily: t.sans,
      display: "grid",
      gridTemplateColumns: "250px 1fr 320px",
      gridTemplateRows: "42px 1fr 250px 26px",
      gridTemplateAreas: `"top top top" "rail center right" "rail bottom bottom" "status status status"`,
    }}>
      {/* top bar */}
      <header style={{ gridArea: "top", display: "flex", alignItems: "center", gap: 14,
        padding: "0 16px", borderBottom: `1px solid ${t.border}`, background: t.bgPanel }}>
        <strong style={{ fontSize: 15, letterSpacing: 0.5 }}>◆ IMPERIUM</strong>
        <select value={activeId ?? ""} onChange={(e) => setActiveId(e.target.value)}
          style={{ background: t.bgElev, color: t.text, border: `1px solid ${t.border}`,
            borderRadius: 5, padding: "4px 8px", fontSize: 12, fontFamily: t.mono, maxWidth: 260 }}>
          {repos.length === 0 && <option value="">no repositories</option>}
          {repos.map((r) => <option key={r.id} value={r.id}>{r.id}</option>)}
        </select>
        <Btn kind="green" onClick={startRun} disabled={!activeId}>▶ Start Run</Btn>
        {runId && <span style={{ fontSize: 11, color: t.textDim, fontFamily: t.mono }}>run {runId.slice(0, 8)}</span>}
        <div style={{ flex: 1 }} />
        <Btn onClick={() => setPalette(true)}>⌘K</Btn>
        <span style={{ fontSize: 12, color: t.textDim }}>{user?.email}</span>
        <Btn onClick={signOut}>Sign out</Btn>
      </header>

      {/* left rail */}
      <aside style={{ gridArea: "rail", borderRight: `1px solid ${t.border}`, minHeight: 0, overflow: "hidden" }}>
        <RepoRail />
      </aside>

      {/* center */}
      <main style={{ gridArea: "center", minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column",
        borderRight: `1px solid ${t.border}` }}>
        <TabBar tabs={CENTER} active={center} onSelect={setCenter} />
        <div style={{ flex: 1, minHeight: 0 }}>
          {center === "map" && <StructureMapPanel />}
          {center === "changes" && <ChangeReviewPanel />}
          {center === "findings" && <FindingsPanel />}
          {center === "timeline" && <TimelinePanel />}
        </div>
      </main>

      {/* right dock */}
      <aside style={{ gridArea: "right", minHeight: 0, display: "grid", gridTemplateRows: "1fr 1fr 1fr" }}>
        <div style={{ minHeight: 0, borderBottom: `1px solid ${t.border}` }}><PrioritiesPanel /></div>
        <div style={{ minHeight: 0, borderBottom: `1px solid ${t.border}` }}><BusinessRulesPanel /></div>
        <div style={{ minHeight: 0 }}><ClarificationsPanel /></div>
      </aside>

      {/* bottom dock */}
      <section style={{ gridArea: "bottom", minHeight: 0, display: "flex", flexDirection: "column",
        borderTop: `1px solid ${t.border}` }}>
        <TabBar tabs={BOTTOM} active={bottom} onSelect={setBottom} />
        <div style={{ flex: 1, minHeight: 0 }}>
          {bottom === "gatea" && <GateAPanel />}
          {bottom === "decisions" && <DecisionLogPanel />}
          {bottom === "chat" && <ChatPanel />}
          {bottom === "runs" && <RunEventsPanel />}
          {bottom === "comprehension" && <ComprehensionPanel />}
        </div>
      </section>

      {/* status bar */}
      <div style={{ gridArea: "status" }}><StatusBar /></div>

      {palette && <CommandPalette
        onClose={() => setPalette(false)}
        onCommand={(id) => {
          if (id === "run") startRun();
          else if (id.startsWith("c:")) setCenter(id.slice(2) as CenterTab);
          else if (id.startsWith("b:")) setBottom(id.slice(2) as BottomTab);
          setPalette(false);
        }} />}
    </div>
  );
}

function CommandPalette({ onClose, onCommand }: { onClose: () => void; onCommand: (id: string) => void }) {
  const [q, setQ] = useState("");
  const cmds = [
    { id: "run", label: "▶ Start pipeline run" },
    ...CENTER.map((c) => ({ id: `c:${c.id}`, label: `Go to ${c.label}` })),
    ...BOTTOM.map((b) => ({ id: `b:${b.id}`, label: `Open ${b.label}` })),
  ].filter((c) => c.label.toLowerCase().includes(q.toLowerCase()));
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "#0008",
      display: "flex", justifyContent: "center", paddingTop: 120, zIndex: 50 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 480, height: "fit-content",
        background: t.bgElev, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden" }}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type a command…"
          style={{ width: "100%", padding: "12px 14px", background: "transparent", border: "none",
            borderBottom: `1px solid ${t.border}`, color: t.text, fontSize: 14, outline: "none", boxSizing: "border-box" }} />
        <div style={{ maxHeight: 300, overflow: "auto" }}>
          {cmds.map((c) => (
            <div key={c.id} onClick={() => onCommand(c.id)}
              style={{ padding: "9px 14px", fontSize: 13, cursor: "pointer", color: t.text }}
              onMouseEnter={(e) => (e.currentTarget.style.background = t.bgHover)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
              {c.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
