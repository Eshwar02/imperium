// Editor group — open-file tabs plus the Monaco editor showing file content.
import Editor from "@monaco-editor/react";
import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useWorkbench } from "../../context/WorkbenchContext";
import { useContextMenu } from "../../context/ContextMenuContext";
import { useTheme } from "../../context/ThemeContext";
import { fileIcon, monacoLanguage } from "../../lib/fileIcons";
import { t } from "../../theme";
import { useRepo } from "../../context/RepoContext";
import GraphCanvas from "./GraphCanvas";
import AgentGraph from "./AgentGraph";
import type { OpenEditor } from "../../context/WorkbenchContext";

/** Non-file editor kinds render a graph surface, not the Monaco text editor. */
function isGraphKind(kind: OpenEditor["kind"]): boolean {
  return kind === "module-map" || kind === "api-map" || kind === "agent-graph";
}

export default function EditorArea() {
  const { editors, activePath, setActivePath, closeFile, closeOthers, closeAll } = useWorkbench();
  const { runId } = useRepo();
  const menu = useContextMenu();
  const { theme } = useTheme();
  // path -> { content, binary, loading, error }
  const [cache, setCache] = useState<Record<string, { content: string; binary: boolean; loading: boolean; error?: string }>>({});

  const active = editors.find((e) => e.path === activePath) ?? null;

  useEffect(() => {
    if (!active || isGraphKind(active.kind)) return;
    if (cache[active.path] && !cache[active.path].loading) return;
    setCache((c) => ({ ...c, [active.path]: { content: "", binary: false, loading: true } }));
    api.fileContent(active.repoId, active.path)
      .then((r) => setCache((c) => ({ ...c, [active.path]: { content: r.content, binary: r.binary, loading: false } })))
      .catch((e) => setCache((c) => ({ ...c, [active.path]: { content: "", binary: false, loading: false, error: String(e?.message ?? e) } })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.path, active?.repoId]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0, background: t.bg }}>
      {/* tab strip */}
      <div style={{ display: "flex", background: "#0a0d12", borderBottom: `1px solid ${t.border}`,
        overflowX: "auto", flexShrink: 0, minHeight: 35 }}>
        {editors.map((e) => {
          const sel = e.path === activePath;
          const isFile = !isGraphKind(e.kind);
          return (
            <div key={e.path} onClick={() => setActivePath(e.path)} title={e.path}
              onAuxClick={(ev) => { if (ev.button === 1) { ev.preventDefault(); closeFile(e.path); } }}
              onContextMenu={(ev) => menu.open(ev, [
                { label: "Close", hint: "Ctrl+W", onClick: () => closeFile(e.path) },
                { label: "Close Others", disabled: editors.length < 2, onClick: () => closeOthers(e.path) },
                { label: "Close All", onClick: closeAll },
                { separator: true },
                { label: "Copy Path", disabled: !isFile, onClick: () => navigator.clipboard?.writeText(e.path) },
              ])}
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 10px", fontSize: 13,
                cursor: "pointer", whiteSpace: "nowrap", fontFamily: t.sans,
                background: sel ? t.bg : "transparent", color: sel ? t.text : t.textDim,
                borderRight: `1px solid ${t.border}`, borderTop: sel ? `1px solid ${t.accent}` : "1px solid transparent" }}>
              <span>{e.kind === "agent-graph" ? "⧉" : isGraphKind(e.kind) ? "◈" : fileIcon(e.name)}</span>
              <span>{e.name}</span>
              <span onClick={(ev) => { ev.stopPropagation(); closeFile(e.path); }}
                style={{ marginLeft: 4, color: t.textDim, fontSize: 14, lineHeight: 1 }}
                onMouseEnter={(ev) => (ev.currentTarget.style.color = t.text)}
                onMouseLeave={(ev) => (ev.currentTarget.style.color = t.textDim)}>×</span>
            </div>
          );
        })}
      </div>

      {/* breadcrumbs */}
      {active && !isGraphKind(active.kind) && <Breadcrumbs path={active.path} name={active.name} />}

      {/* body */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {!active && <Welcome />}
        {active && active.kind === "module-map" && <GraphCanvas repoId={active.repoId} layer="arch" />}
        {active && active.kind === "api-map" && <GraphCanvas repoId={active.repoId} layer="api" />}
        {active && active.kind === "agent-graph" && <AgentGraph runId={runId} />}
        {active && !isGraphKind(active.kind) && (() => {
          const st = cache[active.path];
          if (!st || st.loading) return <Center>Loading {active.name}…</Center>;
          if (st.error) return <Center color={t.red}>Failed to open: {st.error}</Center>;
          if (st.binary) return <Center>Binary file — cannot display.</Center>;
          return (
            <Editor
              key={active.path}
              height="100%"
              theme={theme === "dark" ? "vs-dark" : "light"}
              path={active.path}
              defaultLanguage={monacoLanguage(active.name)}
              value={st.content}
              options={{
                readOnly: true, fontSize: 13, minimap: { enabled: true },
                scrollBeyondLastLine: false, automaticLayout: true,
                fontFamily: "'JetBrains Mono', 'SF Mono', Menlo, monospace",
                renderWhitespace: "selection",
              }}
            />
          );
        })()}
      </div>
    </div>
  );
}

// VS Code-style path breadcrumbs: clickable segments separated by chevrons.
function Breadcrumbs({ path, name }: { path: string; name: string }) {
  const segments = path.split("/").filter(Boolean);
  return (
    <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 2, padding: "3px 14px",
      fontSize: 12, color: t.textDim, borderBottom: `1px solid ${t.border}`, background: t.bg }}>
      {segments.map((seg, i) => {
        const last = i === segments.length - 1;
        return (
          <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
            {i > 0 && <span style={{ color: t.border, margin: "0 2px" }}>›</span>}
            <span style={{ color: last ? t.text : t.textDim, display: "inline-flex", alignItems: "center", gap: 4 }}>
              {last && <span>{fileIcon(name)}</span>}
              {seg}
            </span>
          </span>
        );
      })}
    </div>
  );
}

function Center({ children, color = t.textDim }: { children: React.ReactNode; color?: string }) {
  return <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color, fontSize: 13 }}>{children}</div>;
}

function Welcome() {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", color: t.textDim, gap: 10 }}>
      <div style={{ fontSize: 42, letterSpacing: 2, color: t.text, opacity: 0.85 }}>◆ IMPERIUM</div>
      <div style={{ fontSize: 14 }}>Enterprise Knowledge Operating System</div>
      <div style={{ fontSize: 12, marginTop: 8 }}>Open a file from the Explorer, or press <Kbd>Ctrl</Kbd>+<Kbd>P</Kbd> to search files.</div>
      <div style={{ fontSize: 12 }}>Press <Kbd>Ctrl</Kbd>+<Kbd>Shift</Kbd>+<Kbd>P</Kbd> for the command palette · <Kbd>Ctrl</Kbd>+<Kbd>`</Kbd> for the panel.</div>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd style={{ background: t.bgElev, border: `1px solid ${t.border}`, borderRadius: 4,
    padding: "1px 5px", fontSize: 11, fontFamily: t.mono, color: t.text }}>{children}</kbd>;
}
