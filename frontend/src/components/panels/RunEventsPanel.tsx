// Run events — start a run, stream its live event log, and resume gates.
import { useEffect, useRef, useState } from "react";
import { PanelShell, Empty, Badge, Btn, Row } from "../ui";
import { useRepo } from "../../context/RepoContext";
import { api, type Category, type GateDecision } from "../../api/client";
import { t } from "../../theme";

const CATEGORIES: Category[] = ["security", "performance", "modernization", "integration", "documentation"];

function fmt(e: Record<string, unknown>): string {
  try { return JSON.stringify(e); } catch { return String(e); }
}
function statusColor(s: string): string {
  const v = s.toLowerCase();
  if (v.includes("complete") || v.includes("success") || v.includes("done")) return t.green;
  if (v.includes("fail") || v.includes("error")) return t.red;
  if (v.includes("wait") || v.includes("pause") || v.includes("gate")) return t.yellow;
  return t.textDim;
}

export default function RunEventsPanel() {
  const { activeId, runId, setRunId } = useRepo();
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const [status, setStatus] = useState<string>("");
  const [starting, setStarting] = useState(false);
  const [resuming, setResuming] = useState(false);
  const logRef = useRef<HTMLDivElement | null>(null);

  // Reset log when the run changes, then stream events.
  useEffect(() => {
    if (!runId) { setEvents([]); setStatus(""); return; }
    setEvents([]);
    const ctrl = new AbortController();
    api.runEvents(runId, (e) => {
      setEvents((prev) => [...prev, e]);
      const s = e.status;
      if (typeof s === "string") setStatus(s);
    }, ctrl.signal).catch(() => undefined);
    // Best-effort initial status.
    api.getRun(runId).then((r) => { if (typeof r.status === "string") setStatus(r.status); }).catch(() => undefined);
    return () => ctrl.abort();
  }, [runId]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events]);

  if (!activeId) return <PanelShell title="Run Events"><Empty>Select a repository.</Empty></PanelShell>;

  async function startRun() {
    if (!activeId) return;
    setStarting(true);
    try {
      const { run_id } = await api.startRun(activeId);
      setRunId(run_id);
    } catch { /* ignore */ } finally { setStarting(false); }
  }

  async function resumeGate() {
    if (!runId) return;
    setResuming(true);
    try {
      const votes = CATEGORIES.reduce((acc, c) => { acc[c] = "approve"; return acc; }, {} as Record<string, GateDecision>);
      await api.resumeRun(runId, votes);
      const r = await api.getRun(runId);
      if (typeof r.status === "string") setStatus(r.status);
    } catch { /* ignore */ } finally { setResuming(false); }
  }

  return (
    <PanelShell
      title="Run Events"
      right={runId ? <Badge color={statusColor(status)}>{status || "running"}</Badge> : undefined}
    >
      {!runId ? (
        <Btn kind="primary" onClick={startRun} disabled={starting}>{starting ? "Starting…" : "▶ Start run"}</Btn>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0, gap: 8 }}>
          <div style={{ fontSize: 11, color: t.textDim, fontFamily: t.mono, wordBreak: "break-all" }}>run {runId}</div>
          <div
            ref={logRef}
            style={{ flex: 1, minHeight: 80, overflow: "auto", background: t.bg, border: `1px solid ${t.border}`, borderRadius: 6, padding: 8, fontFamily: t.mono, fontSize: 11, color: t.text }}
          >
            {events.length === 0 && <span style={{ color: t.textDim }}>Waiting for events…</span>}
            {events.map((e, i) => (
              <div key={i} style={{ borderBottom: `1px solid ${t.border}33`, padding: "2px 0", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{fmt(e)}</div>
            ))}
          </div>
          <div style={{ borderTop: `1px solid ${t.border}`, paddingTop: 8, flexShrink: 0 }}>
            <Row style={{ flexWrap: "wrap", marginBottom: 6 }}>
              {CATEGORIES.map((c) => <Badge key={c} color={t.green}>{c}: approve</Badge>)}
            </Row>
            <Btn kind="green" onClick={resumeGate} disabled={resuming}>{resuming ? "Resuming…" : "Resume gate (approve all)"}</Btn>
          </div>
        </div>
      )}
    </PanelShell>
  );
}
