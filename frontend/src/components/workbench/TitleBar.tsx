// Title/menu bar — VS Code-style menus (File/Edit/View/…) with real actions where
// they map onto Imperium, plus the active-repo picker and command-palette entry.
import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useRepo } from "../../context/RepoContext";
import { useWorkbench } from "../../context/WorkbenchContext";
import { api } from "../../api/client";
import { t } from "../../theme";

interface MenuItem { label: string; action?: () => void; sep?: boolean }

function Menu({ label, items, open, onOpen }: {
  label: string; items: MenuItem[]; open: boolean; onOpen: (v: boolean) => void;
}) {
  return (
    <div style={{ position: "relative" }}>
      <div onClick={() => onOpen(!open)} onMouseEnter={() => onOpen(open || false)}
        style={{ padding: "3px 8px", fontSize: 13, cursor: "pointer",
          color: t.text, background: open ? t.bgHover : "transparent", borderRadius: 3 }}>
        {label}
      </div>
      {open && (
        <div style={{ position: "absolute", top: "100%", left: 0, minWidth: 220, zIndex: 100,
          background: t.bgElev, border: `1px solid ${t.border}`, borderRadius: 6, padding: "4px 0",
          boxShadow: "0 8px 24px #000a" }}>
          {items.map((it, i) => it.sep ? (
            <div key={i} style={{ height: 1, background: t.border, margin: "4px 0" }} />
          ) : (
            <div key={i} onClick={() => { it.action?.(); onOpen(false); }}
              style={{ padding: "5px 14px", fontSize: 13, color: t.text, cursor: "pointer" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = t.bgHover)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
              {it.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TitleBar({ onPalette }: { onPalette: () => void }) {
  const { user, signOut } = useAuth();
  const { repos, activeId, setActiveId, setRunId } = useRepo();
  const { toggleSidebar, togglePanel, toggleChat, setView } = useWorkbench();
  const [open, setOpen] = useState<string | null>(null);

  const startRun = async () => {
    if (!activeId) return;
    const r = await api.startRun(activeId);
    setRunId(r.run_id);
    setView("run");
  };

  const menus: Record<string, MenuItem[]> = {
    File: [
      { label: "Command Palette…", action: onPalette },
      { label: "Open Explorer", action: () => setView("explorer") },
      { sep: true, label: "" },
      { label: "Sign out", action: signOut },
    ],
    View: [
      { label: "Toggle Primary Sidebar", action: toggleSidebar },
      { label: "Toggle Panel", action: togglePanel },
      { label: "Toggle Chat", action: toggleChat },
      { sep: true, label: "" },
      { label: "Explorer", action: () => setView("explorer") },
      { label: "Search", action: () => setView("search") },
      { label: "Source Control", action: () => setView("scm") },
      { label: "Imperium Intelligence", action: () => setView("intel") },
    ],
    Run: [
      { label: "Start Pipeline Run", action: startRun },
      { label: "Run & Pipeline View", action: () => setView("run") },
    ],
    Help: [
      { label: "Imperium — Enterprise Knowledge OS" },
      { label: "API Docs (/docs)", action: () => window.open("/docs", "_blank") },
    ],
  };

  return (
    <div onMouseLeave={() => setOpen(null)}
      style={{ display: "flex", alignItems: "center", gap: 4, height: 34, padding: "0 8px",
        background: "#0a0d12", borderBottom: `1px solid ${t.border}`, flexShrink: 0 }}>
      <strong style={{ fontSize: 13, letterSpacing: 0.5, color: t.text, marginRight: 8 }}>◆</strong>
      {Object.entries(menus).map(([label, items]) => (
        <Menu key={label} label={label} items={items}
          open={open === label} onOpen={(v) => setOpen(v ? label : null)} />
      ))}

      <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
        <select value={activeId ?? ""} onChange={(e) => setActiveId(e.target.value)}
          style={{ background: t.bgElev, color: t.text, border: `1px solid ${t.border}`, borderRadius: 5,
            padding: "3px 10px", fontSize: 12, fontFamily: t.mono, maxWidth: 420, textAlign: "center" }}>
          {repos.length === 0 && <option value="">no repositories</option>}
          {repos.map((r) => (
            <option key={r.id} value={r.id}>
              {(r.url?.split("/").pop() ?? r.id)} · {r.id.slice(0, 8)}
            </option>
          ))}
        </select>
      </div>

      <div onClick={onPalette} title="Command Palette (Ctrl+Shift+P)"
        style={{ fontSize: 12, color: t.textDim, cursor: "pointer", padding: "0 8px" }}>⌘K</div>
      <span style={{ fontSize: 12, color: t.textDim }}>{user?.email}</span>
    </div>
  );
}
