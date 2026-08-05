// Gate A — human approval of analysis findings per category before the pipeline proceeds.
import { useState } from "react";
import { t, catColor } from "../../theme";
import { PanelShell, Empty, Badge, Btn, Row } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api, type Vote, type Category, type GateDecision } from "../../api/client";

const ALL_CATEGORIES: Category[] = ["security", "performance", "modernization", "integration", "documentation"];
const DECISIONS: GateDecision[] = ["approve", "reject", "defer"];

export default function GateAPanel() {
  const { activeId } = useRepo();
  const { data, loading, error } = useAsync(
    () => (activeId ? api.analysis(activeId) : Promise.resolve(null)),
    [activeId],
  );

  const [votes, setVotes] = useState<Record<string, GateDecision>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [submitErr, setSubmitErr] = useState<string | null>(null);

  if (!activeId) return <PanelShell title="Gate A"><Empty>No repository selected.</Empty></PanelShell>;

  const findings = data?.findings ?? [];
  const derived = Array.from(new Set(findings.map((f) => f.category)));
  const categories: Category[] = derived.length ? derived : ALL_CATEGORIES;
  const allVoted = categories.every((c) => votes[c]);

  async function submit() {
    setSubmitting(true);
    setResult(null);
    setSubmitErr(null);
    try {
      const payload: Vote[] = categories.map((category) => ({ category, decision: votes[category] }));
      await api.gateA(activeId!, payload);
      setResult("Gate A submitted.");
    } catch (e) {
      setSubmitErr(String((e as Error)?.message ?? e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PanelShell title="Gate A">
      {loading && <Empty>Loading findings…</Empty>}
      {error && <div style={{ color: t.red, fontSize: 13, padding: 12 }}>{error}</div>}

      {!loading && !error && categories.map((category) => (
        <Row key={category} style={{ padding: "8px 4px", borderBottom: `1px solid ${t.border}`, justifyContent: "space-between", flexWrap: "wrap" }}>
          <Badge color={catColor[category]}>{category}</Badge>
          <Row style={{ gap: 12 }}>
            {DECISIONS.map((d) => (
              <label key={d} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: t.text, cursor: "pointer" }}>
                <input
                  type="radio"
                  name={category}
                  value={d}
                  checked={votes[category] === d}
                  onChange={() => setVotes((v) => ({ ...v, [category]: d }))}
                />
                {d}
              </label>
            ))}
          </Row>
        </Row>
      ))}

      {!loading && !error && (
        <div style={{ marginTop: 12 }}>
          <Btn kind="primary" onClick={submit} disabled={!allVoted || submitting}>
            {submitting ? "Submitting…" : "Submit Gate A"}
          </Btn>
          {result && <div style={{ color: t.green, fontSize: 12, marginTop: 8 }}>{result}</div>}
          {submitErr && <div style={{ color: t.red, fontSize: 12, marginTop: 8 }}>{submitErr}</div>}
        </div>
      )}
    </PanelShell>
  );
}
