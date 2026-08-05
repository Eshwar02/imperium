// Status bar — thin fixed footer: health dot, token usage, active repo, run status.
import { useEffect, useState } from "react";
import { useRepo } from "../../context/RepoContext";
import { api } from "../../api/client";
import { t } from "../../theme";

function sumNumbers(o: Record<string, unknown>): number | null {
  let total = 0;
  let found = false;
  for (const v of Object.values(o)) {
    if (typeof v === "number") { total += v; found = true; }
  }
  return found ? total : null;
}

export default function StatusBar() {
  const { activeId, runId } = useRepo();
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [tokens, setTokens] = useState<string>("n/a");
  const [runStatus, setRunStatus] = useState<string>("");

  // Poll health every 10s.
  useEffect(() => {
    let alive = true;
    const check = () => api.health()
      .then((h) => { if (alive) setHealthy(h.status === "ok" || h.status === "healthy" || !!h.status); })
      .catch(() => { if (alive) setHealthy(false); });
    check();
    const id = setInterval(check, 10000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  // Best-effort token usage.
  useEffect(() => {
    let alive = true;
    api.usage()
      .then((u) => {
        if (!alive) return;
        const total = u && typeof u === "object" ? sumNumbers(u) : null;
        setTokens(total == null ? "n/a" : String(total));
      })
      .catch(() => { if (alive) setTokens("n/a"); });
    return () => { alive = false; };
  }, []);

  // Run status when a run is active.
  useEffect(() => {
    if (!runId) { setRunStatus(""); return; }
    let alive = true;
    api.getRun(runId)
      .then((r) => { if (alive) setRunStatus(typeof r.status === "string" ? r.status : ""); })
      .catch(() => { if (alive) setRunStatus(""); });
    return () => { alive = false; };
  }, [runId]);

  const dot = healthy == null ? t.textDim : healthy ? t.green : t.red;
  const repoLabel = activeId ? (activeId.length > 12 ? `${activeId.slice(0, 12)}…` : activeId) : "—";

  return (
    <div style={{
      height: 26, flexShrink: 0, display: "flex", alignItems: "center", gap: 16,
      padding: "0 12px", background: t.bgPanel, borderTop: `1px solid ${t.border}`,
      fontFamily: t.mono, fontSize: 11, color: t.textDim,
    }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: dot }} />
        {healthy == null ? "…" : healthy ? "healthy" : "down"}
      </span>
      <span>tokens: {tokens}</span>
      <span>repo: {repoLabel}</span>
      {runId && <span>run: {runStatus || "…"}</span>}
    </div>
  );
}
