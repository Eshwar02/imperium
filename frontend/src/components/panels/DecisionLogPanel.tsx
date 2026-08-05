// Decision log — audit table of gate verdicts for the active repo.
import { PanelShell, Empty, Badge, Btn } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api, type Decision } from "../../api/client";
import { t } from "../../theme";

function verdictColor(v?: string): string {
  const s = (v ?? "").toLowerCase();
  if (s === "approve") return t.green;
  if (s === "reject") return t.red;
  if (s === "defer") return t.yellow;
  return t.textDim;
}

function shortDate(s?: string): string {
  if (!s) return "—";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

const th: React.CSSProperties = {
  textAlign: "left", padding: "5px 8px", color: t.textDim, fontSize: 11,
  textTransform: "uppercase", letterSpacing: 0.4, borderBottom: `1px solid ${t.border}`, whiteSpace: "nowrap",
};
const td: React.CSSProperties = { padding: "6px 8px", fontSize: 12, color: t.text, borderBottom: `1px solid ${t.border}55`, verticalAlign: "top" };

export default function DecisionLogPanel() {
  const { activeId } = useRepo();
  const { data, loading, error, reload } = useAsync(
    () => (activeId ? api.decisions(activeId) : Promise.resolve({ decisions: [] })),
    [activeId]
  );

  if (!activeId) return <PanelShell title="Decision Log"><Empty>Select a repository.</Empty></PanelShell>;

  const decisions: Decision[] = data?.decisions ?? [];

  return (
    <PanelShell
      title="Decision Log"
      right={<Btn onClick={reload} disabled={loading}>{loading ? "…" : "⟳ Reload"}</Btn>}
    >
      {error && <Empty>Error: {error}</Empty>}
      {!error && decisions.length === 0 && !loading && <Empty>No decisions recorded.</Empty>}
      {decisions.length > 0 && (
        <table style={{ borderCollapse: "collapse", width: "100%", fontFamily: t.sans }}>
          <thead>
            <tr>
              <th style={th}>When</th>
              <th style={th}>Category</th>
              <th style={th}>Verdict</th>
              <th style={th}>Gate</th>
              <th style={th}>Summary</th>
              <th style={th}>Approver</th>
            </tr>
          </thead>
          <tbody>
            {decisions.map((d, i) => (
              <tr key={i}>
                <td style={{ ...td, whiteSpace: "nowrap", color: t.textDim }}>{shortDate(d.created_at)}</td>
                <td style={td}>{d.category ?? "—"}</td>
                <td style={td}><Badge color={verdictColor(d.verdict)}>{d.verdict ?? "—"}</Badge></td>
                <td style={td}>{d.gate ?? "—"}</td>
                <td style={{ ...td, maxWidth: 340 }}>{d.change_summary ?? "—"}</td>
                <td style={{ ...td, color: t.textDim }}>{d.approver ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </PanelShell>
  );
}
