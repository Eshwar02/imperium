// Priorities panel — files ranked by score with a horizontal score bar.
import { PanelShell, Empty, Btn } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api } from "../../api/client";
import { t } from "../../theme";

export default function PrioritiesPanel() {
  const { activeId } = useRepo();
  const { data, loading, error, reload } = useAsync(
    () => (activeId ? api.priorities(activeId) : Promise.resolve({ priorities: [] })),
    [activeId],
  );

  if (!activeId) return <PanelShell title="Priorities"><Empty>Select a repository.</Empty></PanelShell>;

  const priorities = [...(data?.priorities ?? [])].sort((a, b) => b.score - a.score);
  const max = priorities.reduce((m, p) => Math.max(m, p.score), 0) || 1;
  const overOne = priorities.some((p) => p.score > 1);

  return (
    <PanelShell title="Priorities" right={<Btn onClick={reload}>↻</Btn>}>
      {loading && <Empty>Loading…</Empty>}
      {error && <Empty>{error}</Empty>}
      {!loading && !error && priorities.length === 0 && <Empty>No priorities.</Empty>}
      {!loading && !error && priorities.map((p, i) => {
        const pct = Math.max(0, Math.min(1, overOne ? p.score / max : p.score)) * 100;
        return (
          <div key={`${p.file_path}-${i}`} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 4px" }}>
            <span style={{ color: t.textDim, fontSize: 12, width: 24, textAlign: "right", flexShrink: 0 }}>{i + 1}</span>
            <span style={{ fontFamily: t.mono, fontSize: 12, color: t.text, flex: 1, minWidth: 0,
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={p.file_path}>{p.file_path}</span>
            <div style={{ width: 120, height: 8, background: t.bgElev, borderRadius: 4, overflow: "hidden", flexShrink: 0 }}>
              <div style={{ width: `${pct}%`, height: "100%", background: t.accent }} />
            </div>
            <span style={{ fontFamily: t.mono, fontSize: 11, color: t.textDim, width: 44, textAlign: "right", flexShrink: 0 }}>
              {p.score.toFixed(2)}
            </span>
          </div>
        );
      })}
    </PanelShell>
  );
}
