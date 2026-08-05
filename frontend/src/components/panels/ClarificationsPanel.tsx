// Clarifications panel — HITL questions answered inline, then reloaded.
import { useState } from "react";
import { PanelShell, Empty, Btn, Row } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api } from "../../api/client";
import { t } from "../../theme";

export default function ClarificationsPanel() {
  const { activeId } = useRepo();
  const { data, loading, error, reload } = useAsync(
    () => (activeId ? api.clarifications(activeId) : Promise.resolve({ questions: [] })),
    [activeId],
  );
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  if (!activeId) return <PanelShell title="Clarifications"><Empty>Select a repository.</Empty></PanelShell>;

  const questions = data?.questions ?? [];

  async function submit(rule_id: string) {
    const text = answers[rule_id]?.trim();
    if (!text) return;
    setBusy(rule_id);
    try {
      await api.answerClarification(activeId!, rule_id, text);
      setAnswers((a) => ({ ...a, [rule_id]: "" }));
      reload();
    } finally {
      setBusy(null);
    }
  }

  return (
    <PanelShell title="Clarifications" right={<Btn onClick={reload}>↻</Btn>}>
      {loading && <Empty>Loading…</Empty>}
      {error && <Empty>{error}</Empty>}
      {!loading && !error && questions.length === 0 && <Empty>No open clarifications.</Empty>}
      {!loading && !error && questions.map((q, i) => {
        const key = q.rule_id ?? String(i);
        return (
          <div key={key} style={{ padding: 10, marginBottom: 8, background: t.bgElev,
            border: `1px solid ${t.border}`, borderRadius: 6 }}>
            <div style={{ fontSize: 13, color: t.text, marginBottom: 8, lineHeight: 1.4 }}>
              {q.hitl_question ?? q.statement}
            </div>
            <Row>
              <input
                value={answers[key] ?? ""}
                onChange={(e) => setAnswers((a) => ({ ...a, [key]: e.target.value }))}
                placeholder="Your answer…"
                style={{ flex: 1, minWidth: 0, fontFamily: t.sans, fontSize: 12, color: t.text,
                  background: t.bg, border: `1px solid ${t.border}`, borderRadius: 5, padding: "5px 8px" }}
              />
              <Btn kind="primary" disabled={!q.rule_id || busy === key || !(answers[key] ?? "").trim()}
                onClick={() => q.rule_id && submit(q.rule_id)}>
                {busy === key ? "…" : "Answer"}
              </Btn>
            </Row>
          </div>
        );
      })}
    </PanelShell>
  );
}
