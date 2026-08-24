// Activity bar — the vertical icon strip that switches the primary sidebar view.
import { useAuth } from "../../context/AuthContext";
import { useRepo } from "../../context/RepoContext";
import { useWorkbench, type ActivityView } from "../../context/WorkbenchContext";
import { useTheme } from "../../context/ThemeContext";
import { useContextMenu } from "../../context/ContextMenuContext";
import Tooltip from "../ui/Tooltip";
import { t } from "../../theme";

// Small notification dot pinned to the corner of an activity icon.
function Badge() {
  return (
    <span style={{ position: "absolute", top: 10, right: 8, width: 8, height: 8, borderRadius: "50%",
      background: t.green, border: `1px solid #0a0d12` }} />
  );
}

const ITEMS: { id: ActivityView; icon: string; label: string }[] = [
  { id: "projects", icon: "🗂", label: "Projects" },
  { id: "explorer", icon: "🗎", label: "Explorer" },
  { id: "search", icon: "🔍", label: "Search" },
  { id: "scm", icon: "⑃", label: "Source Control" },
  { id: "run", icon: "▷", label: "Run & Pipeline" },
  { id: "intel", icon: "◈", label: "Imperium Intelligence" },
];

export default function ActivityBar() {
  const { view, setView, sidebarOpen, chatOpen, toggleChat } = useWorkbench();
  const { signOut } = useAuth();
  const { runId } = useRepo();
  const { theme, setTheme } = useTheme();
  const menu = useContextMenu();

  const openSettings = (e: React.MouseEvent) => menu.open(e, [
    { label: `${theme === "dark" ? "✓ " : "   "}Dark Theme`, onClick: () => setTheme("dark") },
    { label: `${theme === "light" ? "✓ " : "   "}Light Theme`, onClick: () => setTheme("light") },
    { separator: true },
    { label: "Sign Out", danger: true, onClick: signOut },
  ]);

  const iconBtn = (active: boolean): React.CSSProperties => ({
    width: 48, height: 48, display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: 20, cursor: "pointer", color: active ? t.text : t.textDim,
    borderLeft: `2px solid ${active ? t.text : "transparent"}`, background: "transparent",
    position: "relative",
  });

  return (
    <div style={{
      width: 48, background: "#0a0d12", display: "flex", flexDirection: "column",
      alignItems: "center", borderRight: `1px solid ${t.border}`, flexShrink: 0,
    }}>
      {ITEMS.map((it) => (
        <Tooltip key={it.id} label={it.label} side="right">
          <div onClick={() => setView(it.id)} style={iconBtn(view === it.id && sidebarOpen)}>
            {it.icon}
            {it.id === "run" && runId && <Badge />}
          </div>
        </Tooltip>
      ))}
      <div style={{ flex: 1 }} />
      <Tooltip label="Toggle Chat" side="right">
        <div onClick={toggleChat} style={iconBtn(chatOpen)}>💬</div>
      </Tooltip>
      <Tooltip label="Sign out" side="right">
        <div onClick={signOut} style={iconBtn(false)}>⏻</div>
      </Tooltip>
      <Tooltip label="Manage (Settings)" side="right">
        <div onClick={openSettings} onContextMenu={openSettings} style={iconBtn(false)}>⚙</div>
      </Tooltip>
    </div>
  );
}
