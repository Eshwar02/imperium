// RepoRail — the full left sidebar: ingest a repo, pick the active one,
// start an analysis run, and browse the repository hierarchy tree.
import { useState } from "react";
import { t } from "../../theme";
import { Empty, Badge, Btn, Row } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api } from "../../api/client";

// ---- Section header ---------------------------------------------------------
function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ borderBottom: `1px solid ${t.border}`, padding: "10px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
      <span style={{ fontSize: 11, letterSpacing: 0.6, textTransform: "uppercase", color: t.textDim, fontWeight: 700 }}>{label}</span>
      {children}
    </div>
  );
}

// ---- Hierarchy tree (defensive, TS-strict) ----------------------------------
function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function TreeNode({ nodeKey, value, depth }: { nodeKey: string; value: unknown; depth: number }) {
  const [open, setOpen] = useState(depth < 1);
  const indent = { paddingLeft: depth * 12 };

  // Expandable: arrays and plain objects.
  if (Array.isArray(value) || isRecord(value)) {
    const entries: [string, unknown][] = Array.isArray(value)
      ? value.map((v, i) => [String(i), v])
      : Object.entries(value);
    return (
      <div style={indent}>
        <div
          onClick={() => setOpen((o) => !o)}
          style={{ cursor: "pointer", fontSize: 12, color: t.text, padding: "1px 0", userSelect: "none", whiteSpace: "nowrap" }}
        >
          <span style={{ color: t.textDim, marginRight: 4 }}>{open ? "▾" : "▸"}</span>
          {nodeKey}
          <span style={{ color: t.textDim, marginLeft: 6, fontSize: 11 }}>
            {Array.isArray(value) ? `[${entries.length}]` : `{${entries.length}}`}
          </span>
        </div>
        {open &&
          entries.map(([k, v]) => <TreeNode key={k} nodeKey={k} value={v} depth={depth + 1} />)}
      </div>
    );
  }

  // Primitive / null leaf.
  const shown = value === null ? "null" : String(value);
  return (
    <div style={{ ...indent, fontSize: 12, padding: "1px 0", whiteSpace: "nowrap" }}>
      <span style={{ color: t.textDim, marginLeft: 14 }}>{nodeKey}: </span>
      <span style={{ color: t.text, fontFamily: t.mono }}>{shown}</span>
    </div>
  );
}

function HierarchyTree({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return <Empty>No hierarchy.</Empty>;
  return (
    <div style={{ fontFamily: t.sans }}>
      {entries.map(([k, v]) => <TreeNode key={k} nodeKey={k} value={v} depth={0} />)}
    </div>
  );
}

// ---- Main panel -------------------------------------------------------------
export default function RepoRail() {
  const { repos, activeId, setActiveId, reloadRepos, runId, setRunId } = useRepo();

  // 1) Ingest
  const [url, setUrl] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestErr, setIngestErr] = useState<string | null>(null);
  async function onIngest() {
    if (!url.trim() || ingesting) return;
    setIngesting(true);
    setIngestErr(null);
    try {
      const { repository_id } = await api.ingest(url.trim());
      await reloadRepos();
      setActiveId(repository_id);
      setUrl("");
    } catch (e) {
      setIngestErr(String(e instanceof Error ? e.message : e));
    } finally {
      setIngesting(false);
    }
  }

  // 3) Run
  const [running, setRunning] = useState(false);
  const [runErr, setRunErr] = useState<string | null>(null);
  async function onStartRun() {
    if (!activeId || running) return;
    setRunning(true);
    setRunErr(null);
    try {
      const { run_id } = await api.startRun(activeId);
      setRunId(run_id);
    } catch (e) {
      setRunErr(String(e instanceof Error ? e.message : e));
    } finally {
      setRunning(false);
    }
  }

  // 4) Hierarchy
  const hierarchy = useAsync<Record<string, unknown>>(
    () => (activeId ? api.hierarchy(activeId) : Promise.resolve({})),
    [activeId],
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%", background: t.bgPanel, overflow: "auto" }}>
      {/* 1) INGEST */}
      <Section label="Ingest">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void onIngest(); }}
          placeholder="git repository URL"
          disabled={ingesting}
          style={{
            fontSize: 12, fontFamily: t.mono, padding: "5px 8px", borderRadius: 5,
            border: `1px solid ${t.border}`, background: t.bg, color: t.text, outline: "none",
          }}
        />
        <Row>
          <Btn kind="primary" onClick={() => void onIngest()} disabled={ingesting || !url.trim()}>
            {ingesting ? "Ingesting…" : "Ingest"}
          </Btn>
          {ingesting && <span style={{ fontSize: 12, color: t.textDim }}>working…</span>}
        </Row>
        {ingestErr && <span style={{ fontSize: 12, color: t.red }}>{ingestErr}</span>}
      </Section>

      {/* 2) REPOSITORIES */}
      <Section label="Repositories">
        {repos.length === 0 ? (
          <Empty>No repositories — ingest one above.</Empty>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {repos.map((r) => {
              const active = r.id === activeId;
              return (
                <div
                  key={r.id}
                  onClick={() => setActiveId(r.id)}
                  style={{
                    cursor: "pointer", padding: "5px 6px", borderRadius: 4,
                    background: active ? t.bgHover : "transparent",
                    borderLeft: `2px solid ${active ? t.accent : "transparent"}`,
                    display: "flex", flexDirection: "column", gap: 4,
                  }}
                >
                  <span style={{ fontSize: 12, fontFamily: t.mono, color: t.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r.id}
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
      </Section>

      {/* 3) RUN */}
      <Section label="Run">
        <Row>
          <Btn kind="green" onClick={() => void onStartRun()} disabled={!activeId || running}>
            {running ? "Starting…" : "▶ Start Run"}
          </Btn>
        </Row>
        {runId && <span style={{ fontSize: 12, fontFamily: t.mono, color: t.textDim }}>run: {runId}</span>}
        {runErr && <span style={{ fontSize: 12, color: t.red }}>{runErr}</span>}
      </Section>

      {/* 4) HIERARCHY */}
      <Section label="Hierarchy">
        {!activeId ? (
          <Empty>Select a repository.</Empty>
        ) : hierarchy.loading ? (
          <span style={{ fontSize: 12, color: t.textDim }}>Loading…</span>
        ) : hierarchy.error ? (
          <span style={{ fontSize: 12, color: t.red }}>{hierarchy.error}</span>
        ) : hierarchy.data ? (
          <HierarchyTree data={hierarchy.data} />
        ) : (
          <Empty>No hierarchy.</Empty>
        )}
      </Section>
    </div>
  );
}
