// Timeline — commit history rendered as a vertical dotted timeline.
import { PanelShell, Empty, Btn } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api } from "../../api/client";
import { t } from "../../theme";

export default function TimelinePanel() {
  const { activeId } = useRepo();

  const { data, loading, error, reload } = useAsync(
    () => (activeId ? api.timeline(activeId) : Promise.resolve({ events: [] })),
    [activeId],
  );

  if (!activeId)
    return (
      <PanelShell title="Timeline">
        <Empty>Select a repository</Empty>
      </PanelShell>
    );

  const events = data?.events ?? [];

  return (
    <PanelShell title="Timeline" right={<Btn onClick={reload} disabled={loading}>↻</Btn>}>
      {error ? (
        <Empty>Error: {error}</Empty>
      ) : loading && !data ? (
        <Empty>Loading…</Empty>
      ) : events.length === 0 ? (
        <Empty>No commits</Empty>
      ) : (
        <div style={{ borderLeft: `1px solid ${t.border}`, marginLeft: 6 }}>
          {events.map((e, i) => (
            <div
              key={`${e.commit_sha}-${i}`}
              style={{ position: "relative", padding: "0 0 14px 18px" }}
            >
              <span
                style={{
                  position: "absolute",
                  left: -5,
                  top: 3,
                  width: 9,
                  height: 9,
                  borderRadius: "50%",
                  background: t.accent,
                  border: `2px solid ${t.bgPanel}`,
                }}
              />
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <span style={{ fontFamily: t.mono, fontSize: 11, color: t.yellow }}>
                  {e.commit_sha.slice(0, 7)}
                </span>
                <span style={{ fontSize: 11, color: t.textDim, fontFamily: t.sans }}>{e.author}</span>
              </div>
              <div style={{ fontSize: 12, color: t.text, fontFamily: t.sans, marginTop: 2 }}>
                {e.summary}
              </div>
            </div>
          ))}
        </div>
      )}
    </PanelShell>
  );
}
