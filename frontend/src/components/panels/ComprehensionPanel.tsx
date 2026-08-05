// Comprehension — per-module understanding scores + record a new score.
import { useState } from "react";
import { PanelShell, Empty, Badge, Btn, Row } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api } from "../../api/client";
import { t } from "../../theme";

interface Item { label: string; score?: number; flagged?: boolean }

function num(v: unknown): number | undefined {
  return typeof v === "number" ? v : undefined;
}

/** Defensively pull a list of module/check items out of an unknown-shaped payload. */
function extract(data: Record<string, unknown> | null): Item[] {
  if (!data || typeof data !== "object") return [];
  let arr: unknown = null;
  if (Array.isArray(data)) arr = data;
  else if (Array.isArray(data.checks)) arr = data.checks;
  else if (Array.isArray(data.modules)) arr = data.modules;
  else if (Array.isArray(data.items)) arr = data.items;
  if (!Array.isArray(arr)) return [];
  return arr.map((raw): Item => {
    if (raw && typeof raw === "object") {
      const o = raw as Record<string, unknown>;
      const label =
        (typeof o.module_path === "string" && o.module_path) ||
        (typeof o.path === "string" && o.path) ||
        (typeof o.name === "string" && o.name) ||
        (typeof o.module === "string" && o.module) ||
        "unknown";
      const score = num(o.comprehension_score) ?? num(o.score);
      const flagged = o.flagged === true || o.needs_review === true;
      return { label, score, flagged };
    }
    return { label: String(raw) };
  });
}

export default function ComprehensionPanel() {
  const { activeId } = useRepo();
  const { data, loading, error, reload } = useAsync(
    () => (activeId ? api.comprehension(activeId) : Promise.resolve({})),
    [activeId]
  );
  const [modulePath, setModulePath] = useState("");
  const [score, setScore] = useState(0.5);
  const [saving, setSaving] = useState(false);

  if (!activeId) return <PanelShell title="Comprehension"><Empty>Select a repository.</Empty></PanelShell>;

  const items = extract(data);

  async function record() {
    const p = modulePath.trim();
    if (!p || !activeId) return;
    setSaving(true);
    try {
      await api.answerComprehension(activeId, p, score);
      setModulePath("");
      reload();
    } catch { /* ignore */ } finally { setSaving(false); }
  }

  return (
    <PanelShell
      title="Comprehension"
      right={<Btn onClick={reload} disabled={loading}>{loading ? "…" : "⟳"}</Btn>}
    >
      {error && <Empty>Error: {error}</Empty>}
      {!error && items.length === 0 && !loading && <Empty>No comprehension data.</Empty>}

      <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 12 }}>
        {items.map((it, i) => (
          <Row key={i} style={{ justifyContent: "space-between", fontSize: 12, padding: "4px 6px", background: t.bgElev, borderRadius: 5 }}>
            <span style={{ fontFamily: t.mono, color: t.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.label}</span>
            <Row>
              {typeof it.score === "number" && <Badge color={it.score < 0.5 ? t.red : it.score < 0.8 ? t.yellow : t.green}>{it.score.toFixed(2)}</Badge>}
              {it.flagged && <Badge color={t.red}>flagged</Badge>}
            </Row>
          </Row>
        ))}
      </div>

      <div style={{ borderTop: `1px solid ${t.border}`, paddingTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
        <input
          value={modulePath}
          onChange={(e) => setModulePath(e.target.value)}
          placeholder="module_path (e.g. src/foo.py)"
          style={{ background: t.bg, color: t.text, border: `1px solid ${t.border}`, borderRadius: 5, padding: "6px 10px", fontSize: 12, fontFamily: t.mono, outline: "none" }}
        />
        <Row>
          <input
            type="range" min={0} max={1} step={0.1} value={score}
            onChange={(e) => setScore(parseFloat(e.target.value))}
            style={{ flex: 1 }}
          />
          <span style={{ fontFamily: t.mono, fontSize: 12, color: t.text, width: 34, textAlign: "right" }}>{score.toFixed(1)}</span>
          <Btn kind="primary" onClick={record} disabled={saving || !modulePath.trim()}>{saving ? "…" : "Record"}</Btn>
        </Row>
      </div>
    </PanelShell>
  );
}
