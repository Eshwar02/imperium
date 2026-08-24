// Activity bar — the vertical icon strip that switches the primary sidebar view.
import { useAuth } from "../../context/AuthContext";
import { useWorkbench, type ActivityView } from "../../context/WorkbenchContext";
import { useTheme } from "../../context/ThemeContext";
import { useContextMenu } from "../../context/ContextMenuContext";
import { t } from "../../theme";

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
        <div key={it.id} title={it.label} onClick={() => setView(it.id)}
          style={iconBtn(view === it.id && sidebarOpen)}>{it.icon}</div>
      ))}
      <div style={{ flex: 1 }} />
      <div title="Toggle Chat" onClick={toggleChat} style={iconBtn(chatOpen)}>💬</div>
      <div title="Sign out" onClick={signOut} style={iconBtn(false)}>⏻</div>
      <div title="Manage (Settings)" onClick={openSettings} onContextMenu={openSettings}
        style={iconBtn(false)}>⚙</div>
    </div>
  );
}
