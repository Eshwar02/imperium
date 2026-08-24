// Status bar — bottom strip: repo/branch/run on the left, editor info on the right.
import { useEffect, useState } from "react";
import { useRepo } from "../../context/RepoContext";
import { useWorkbench } from "../../context/WorkbenchContext";
import { useNotifications } from "../../context/NotificationContext";
import { monacoLanguage } from "../../lib/fileIcons";
import { t } from "../../theme";

export default function StatusBar() {
  const { repos, activeId, runId } = useRepo();
  const { editors, activePath, panelOpen, togglePanel, setPanelTab } = useWorkbench();
  const { notifications, clearAll } = useNotifications();
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/health").then((r) => setOnline(r.ok)).catch(() => setOnline(false));
  }, []);

  const repo = repos.find((r) => r.id === activeId);
  const active = editors.find((e) => e.path === activePath);
  const lang = active ? monacoLanguage(active.name) : "";

  const errors = notifications.filter((n) => n.severity === "error").length;
  const warnings = notifications.filter((n) => n.severity === "warning").length;

  const openProblems = () => { setPanelTab("problems"); if (!panelOpen) togglePanel(); };

  const cell: React.CSSProperties = { padding: "0 8px", display: "flex", alignItems: "center", gap: 4, cursor: "default", height: "100%" };
  const btn: React.CSSProperties = { ...cell, cursor: "pointer" };
  const hover = (on: boolean) => (e: React.MouseEvent<HTMLDivElement>) => (e.currentTarget.style.background = on ? "#ffffff26" : "transparent");

  return (
    <div style={{ height: 22, background: t.accent, color: "#fff", display: "flex", alignItems: "center",
      fontSize: 11, fontFamily: t.sans, flexShrink: 0 }}>
      <div style={cell}>⑃ {repo?.ref ?? "—"}</div>
      <div style={btn} onClick={openProblems} onMouseEnter={hover(true)} onMouseLeave={hover(false)}
        title="Problems">⛔ {errors} ⚠ {warnings}</div>
      <div style={cell}>{online == null ? "…" : online ? "● online" : "○ offline"}</div>
      <div style={cell} title={activeId ?? ""}>{repo ? (repo.url?.split("/").pop() ?? repo.id.slice(0, 8)) : "no repo"}</div>
      {runId && <div style={cell}>▷ run {runId.slice(0, 8)}</div>}
      <div style={{ flex: 1 }} />
      <div style={btn} onClick={togglePanel} onMouseEnter={hover(true)} onMouseLeave={hover(false)}>Panel</div>
      {active && <div style={cell}>{lang}</div>}
      {active && <div style={cell}>UTF-8</div>}
      <div style={btn} onClick={clearAll} onMouseEnter={hover(true)} onMouseLeave={hover(false)}
        title={notifications.length ? "Clear notifications" : "No notifications"}>
        🔔{notifications.length > 0 ? ` ${notifications.length}` : ""}
      </div>
    </div>
  );
}
