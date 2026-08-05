// Findings — analysis results grouped by category, with re-analyze and confidence bars.
import { useState } from "react";
import { PanelShell, Empty, Badge, Btn } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api, type Finding } from "../../api/client";
import { t, catColor } from "../../theme";

export default function FindingsPanel() {
  const { activeId } = useRepo();
  const [busy, setBusy] = useState(false);

  const { data, loading, error, reload } = useAsync(
    () => (activeId ? api.analysis(activeId) : Promise.resolve(null)),
    [activeId],
  );

  if (!activeId)
    return (
      <PanelShell title="Findings">
        <Empty>Select a repository</Empty>
      </PanelShell>
    );

  const reAnalyze = async () => {
    if (!activeId) return;
    setBusy(true);
    try {
      await api.runAnalysis(activeId);
      reload();
    } finally {
      setBusy(false);
    }
  };

  const findings = data?.findings ?? [];
  const groups = findings.reduce<Record<string, Finding[]>>((acc, f) => {
    (acc[f.category] ??= []).push(f);
    return acc;
  }, {});

  return (
    <PanelShell
      title="Findings"
      right={
        <Btn kind="primary" onClick={reAnalyze} disabled={busy || loading}>
          {busy ? "Analyzing…" : "Re-analyze"}
        </Btn>
      }
    >
      {error ? (
        <Empty>Error: {error}</Empty>
      ) : loading && !data ? (
        <Empty>Loading…</Empty>
      ) : findings.length === 0 ? (
        <Empty>No findings</Empty>
      ) : (
        Object.entries(groups).map(([category, items]) => (
          <div key={category} style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8 }}>
              <Badge color={catColor[category]}>
                {category} · {items.length}
              </Badge>
            </div>
            {items.map((f, i) => (
              <div
                key={i}
                style={{
                  background: t.bgElev,
                  border: `1px solid ${t.border}`,
                  borderRadius: 6,
                  padding: 10,
                  marginBottom: 8,
                }}
              >
                <div style={{ color: t.text, fontWeight: 700, fontSize: 13, fontFamily: t.sans }}>
                  {f.title}
                </div>
                <div style={{ color: t.textDim, fontSize: 12, margin: "4px 0 8px", fontFamily: t.sans }}>
                  {f.detail}
                </div>
                <div
                  style={{
                    height: 4,
                    borderRadius: 2,
                    background: t.border,
                    overflow: "hidden",
                    marginBottom: 8,
                  }}
                >
                  <div
                    style={{
                      width: `${Math.max(0, Math.min(1, f.confidence)) * 100}%`,
                      height: "100%",
                      background: catColor[category] ?? t.accent,
                    }}
                  />
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {f.locations.map((loc, j) => (
                    <span
                      key={j}
                      style={{
                        fontSize: 10,
                        fontFamily: t.mono,
                        color: t.textDim,
                        background: t.bgHover,
                        border: `1px solid ${t.border}`,
                        borderRadius: 4,
                        padding: "1px 5px",
                      }}
                    >
                      {loc}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ))
      )}
    </PanelShell>
  );
}
