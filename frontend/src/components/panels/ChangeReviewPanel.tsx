// Change Review — Monaco side-by-side diffs of simulated changes, then Gate B accept/reject.
import { useState } from "react";
import { DiffEditor } from "@monaco-editor/react";
import { t } from "../../theme";
import { PanelShell, Empty, Badge, Btn, Row } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api, type Vote, type Category, type GateDecision } from "../../api/client";
import { parseUnifiedDiff } from "../../lib/diff";

const CATEGORIES: Category[] = ["security", "performance", "modernization", "integration", "documentation"];
const DECISIONS: GateDecision[] = ["approve", "reject", "defer"];

export default function ChangeReviewPanel() {
  const { activeId } = useRepo();
  const { data, loading, error } = useAsync(
    () => (activeId ? api.simulations(activeId) : Promise.resolve({ simulations: [] })),
    [activeId],
  );

  const [votes, setVotes] = useState<Record<Category, GateDecision>>(
    () => Object.fromEntries(CATEGORIES.map((c) => [c, "approve"])) as Record<Category, GateDecision>,
  );
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [submitErr, setSubmitErr] = useState<string | null>(null);

  if (!activeId) return <PanelShell title="Change Review"><Empty>No repository selected.</Empty></PanelShell>;

  async function submit() {
    setSubmitting(true);
    setResult(null);
    setSubmitErr(null);
    try {
      const payload: Vote[] = CATEGORIES.map((category) => ({ category, decision: votes[category] }));
      await api.gateB(activeId!, payload);
      setResult("Gate B submitted — changes accepted.");
    } catch (e) {
      setSubmitErr(String((e as Error)?.message ?? e));
    } finally {
      setSubmitting(false);
    }
  }

  const sims = data?.simulations ?? [];

  return (
    <PanelShell title="Change Review">
      {loading && <Empty>Loading simulated changes…</Empty>}
      {error && <div style={{ color: t.red, fontSize: 13, padding: 12 }}>{error}</div>}
      {!loading && !error && sims.length === 0 && (
        <Empty>No simulated changes yet — run the pipeline to Gate B.</Empty>
      )}

      {sims.map((sim, i) => {
        const { original, modified } = parseUnifiedDiff(sim.diff);
        return (
          <div key={`${sim.file_path}-${i}`} style={{
            border: `1px solid ${t.border}`, background: t.bgElev, borderRadius: 6, marginBottom: 12, overflow: "hidden",
          }}>
            <Row style={{ padding: "8px 10px", borderBottom: `1px solid ${t.border}`, justifyContent: "space-between" }}>
              <span style={{ fontFamily: t.mono, fontSize: 12, color: t.text }}>{sim.file_path}</span>
              <Row style={{ gap: 6 }}>
                <Badge color={sim.confidence_score >= 0.7 ? t.green : t.yellow}>
                  conf {sim.confidence_score.toFixed(2)}
                </Badge>
                <Badge color={sim.safety_passed ? t.green : t.red}>
                  {sim.safety_passed ? "✓ safe" : "✗ blocked"}
                </Badge>
              </Row>
            </Row>
            <DiffEditor
              height="260px"
              theme="vs-dark"
              language="cobol"
              original={original}
              modified={modified}
              options={{ readOnly: true, renderSideBySide: true, minimap: { enabled: false }, scrollBeyondLastLine: false, fontSize: 12 }}
            />
          </div>
        );
      })}

      {sims.length > 0 && (
        <div style={{
          position: "sticky", bottom: 0, background: t.bgPanel, borderTop: `1px solid ${t.border}`,
          padding: "10px 4px", marginTop: 4,
        }}>
          <div style={{ fontSize: 11, letterSpacing: 0.6, textTransform: "uppercase", color: t.textDim, fontWeight: 700, marginBottom: 8 }}>
            Gate B — accept changes
          </div>
          <Row style={{ flexWrap: "wrap", gap: 12 }}>
            {CATEGORIES.map((category) => (
              <label key={category} style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 11, color: t.textDim }}>
                <span style={{ textTransform: "capitalize" }}>{category}</span>
                <select
                  value={votes[category]}
                  onChange={(e) => setVotes((v) => ({ ...v, [category]: e.target.value as GateDecision }))}
                  style={{ fontSize: 12, fontFamily: t.sans, background: t.bgElev, color: t.text, border: `1px solid ${t.border}`, borderRadius: 4, padding: "3px 6px" }}
                >
                  {DECISIONS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
            ))}
            <Btn kind="green" onClick={submit} disabled={submitting} style={{ alignSelf: "flex-end" }}>
              {submitting ? "Submitting…" : "Submit Gate B"}
            </Btn>
          </Row>
          {result && <div style={{ color: t.green, fontSize: 12, marginTop: 8 }}>{result}</div>}
          {submitErr && <div style={{ color: t.red, fontSize: 12, marginTop: 8 }}>{submitErr}</div>}
        </div>
      )}
    </PanelShell>
  );
}
