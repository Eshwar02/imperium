// Projects — add a project by git URL (ingest) and switch the active project.
// The one place to open a repo in the running app. Shares state via
// useProjectActions so the title bar / command palette stay in sync.
import { useEffect, useRef, useState } from "react";
import { t } from "../../theme";
import { Empty, Badge, Btn, Row } from "../ui";
import { useProjectActions } from "../../context/useProjectActions";

function repoName(url: string | null, id: string): string {
  return url?.replace(/\.git$/, "").split("/").pop() || id;
}

export default function ProjectsPanel() {
  const { repos, activeId, setActiveId, ingest, ingesting, error } = useProjectActions();
  const [url, setUrl] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Autofocus when the panel mounts (e.g. via "+ Add Project…").
  useEffect(() => { inputRef.current?.focus(); }, []);

  async function onAdd() {
    if (!url.trim() || ingesting) return;
    try {
      await ingest(url);
      setUrl("");
    } catch { /* error surfaced via `error` */ }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ padding: "8px 12px", fontSize: 11, fontWeight: 700, letterSpacing: 0.6,
        color: t.textDim, textTransform: "uppercase" }}>Projects</div>

      {/* Add by git URL */}
      <div style={{ padding: "0 12px 10px", display: "flex", flexDirection: "column", gap: 8,
        borderBottom: `1px solid ${t.border}` }}>
        <input
          ref={inputRef}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void onAdd(); }}
          placeholder="git repository URL"
          disabled={ingesting}
          aria-label="Git repository URL"
          style={{ fontSize: 12, fontFamily: t.mono, padding: "6px 8px", borderRadius: 5,
            border: `1px solid ${t.border}`, background: t.bg, color: t.text, outline: "none" }}
        />
        <Row>
          <Btn kind="primary" onClick={() => void onAdd()} disabled={ingesting || !url.trim()}>
            {ingesting ? "Adding…" : "＋ Add Project"}
          </Btn>
          {ingesting && <span style={{ fontSize: 12, color: t.textDim }}>working…</span>}
        </Row>
        {error && <span style={{ fontSize: 12, color: t.red }}>{error}</span>}
      </div>

      {/* Repo list */}
      <div style={{ flex: 1, minHeight: 0, overflow: "auto", padding: "8px 8px" }}>
        {repos.length === 0 ? (
          <Empty>No projects yet — add one above.</Empty>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {repos.map((r) => {
              const active = r.id === activeId;
              return (
                <div
                  key={r.id}
                  onClick={() => setActiveId(r.id)}
                  title={r.url ?? r.id}
                  style={{ cursor: "pointer", padding: "6px 8px", borderRadius: 5,
                    background: active ? t.bgHover : "transparent",
                    borderLeft: `2px solid ${active ? t.accent : "transparent"}`,
                    display: "flex", flexDirection: "column", gap: 4 }}
                  onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "#ffffff08"; }}
                  onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "transparent"; }}
                >
                  <span style={{ fontSize: 13, color: t.text, overflow: "hidden",
                    textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {repoName(r.url, r.id)}
                  </span>
                  {r.languages.length > 0 && (
                    <Row style={{ flexWrap: "wrap", gap: 4 }}>
                      {r.languages.map((l) => <Badge key={l}>{l}</Badge>)}
                    </Row>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
