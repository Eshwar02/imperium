// Business rules panel — extracted rules with confidence + verification state.
import { PanelShell, Empty, Badge, Row, Btn } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api } from "../../api/client";
import { t } from "../../theme";

export default function BusinessRulesPanel() {
  const { activeId } = useRepo();
  const { data, loading, error, reload } = useAsync(
    () => (activeId ? api.businessRules(activeId) : Promise.resolve({})),
    [activeId],
  );

  if (!activeId) return <PanelShell title="Business Rules"><Empty>Select a repository.</Empty></PanelShell>;

  const rules = data?.rules ?? data?.business_rules ?? [];

  return (
    <PanelShell title="Business Rules" right={<Btn onClick={reload}>↻</Btn>}>
      {loading && <Empty>Loading…</Empty>}
      {error && <Empty>{error}</Empty>}
      {!loading && !error && rules.length === 0 && <Empty>No business rules.</Empty>}
      {!loading && !error && rules.map((r, i) => (
        <div key={r.id ?? i} style={{ padding: "8px 6px", borderBottom: `1px solid ${t.border}` }}>
          <div style={{ fontSize: 13, color: t.text, marginBottom: 6, lineHeight: 1.4 }}>{r.statement}</div>
          <Row>
            <Badge color={t.yellow}>{`${(r.confidence * 100).toFixed(0)}%`}</Badge>
            <Badge color={r.verified ? t.green : t.textDim}>{r.verified ? "verified" : "unverified"}</Badge>
          </Row>
        </div>
      ))}
    </PanelShell>
  );
}
