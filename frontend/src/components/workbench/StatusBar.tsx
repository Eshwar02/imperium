// Status bar — bottom strip: repo/branch/run on the left, editor info on the right.
import { useEffect, useState } from "react";
import { useRepo } from "../../context/RepoContext";
import { useWorkbench } from "../../context/WorkbenchContext";
import { monacoLanguage } from "../../lib/fileIcons";
import { t } from "../../theme";

export default function StatusBar() {
  const { repos, activeId, runId } = useRepo();
  const { editors, activePath, togglePanel } = useWorkbench();
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/health").then((r) => setOnline(r.ok)).catch(() => setOnline(false));
  }, []);

  const repo = repos.find((r) => r.id === activeId);
  const active = editors.find((e) => e.path === activePath);
  const lang = active ? monacoLanguage(active.name) : "";

  const cell: React.CSSProperties = { padding: "0 8px", display: "flex", alignItems: "center", gap: 4, cursor: "default" };

  return (
    <div style={{ height: 22, background: t.accent, color: "#fff", display: "flex", alignItems: "center",
      fontSize: 11, fontFamily: t.sans, flexShrink: 0 }}>
      <div style={cell}>⑃ {repo?.ref ?? "—"}</div>
      <div style={cell}>{online == null ? "…" : online ? "● online" : "○ offline"}</div>
      <div style={cell} title={activeId ?? ""}>{repo ? (repo.url?.split("/").pop() ?? repo.id.slice(0, 8)) : "no repo"}</div>
      {runId && <div style={cell}>▷ run {runId.slice(0, 8)}</div>}
      <div style={{ flex: 1 }} />
      <div style={{ ...cell, cursor: "pointer" }} onClick={togglePanel}>Panel</div>
      {active && <div style={cell}>{lang}</div>}
      {active && <div style={cell}>UTF-8</div>}
      <div style={cell}>Imperium</div>
    </div>
  );
}
