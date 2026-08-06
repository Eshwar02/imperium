// Output — backend connection + service health snapshot (like VS Code's Output view).
import { useEffect, useState } from "react";
import { t } from "../../theme";

export default function Output() {
  const [log, setLog] = useState<string[]>(["[output] fetching backend status…"]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const now = () => new Date().toLocaleTimeString();
      try {
        const health = await fetch("/health").then((r) => r.json());
        if (alive) setLog((l) => [...l, `[${now()}] health: ${JSON.stringify(health)}`]);
      } catch (e) {
        if (alive) setLog((l) => [...l, `[${now()}] health error: ${String((e as Error).message)}`]);
      }
      try {
        const svc = await fetch("/health/services").then((r) => r.json());
        if (alive) setLog((l) => [...l, `[${now()}] services: ${JSON.stringify(svc)}`]);
      } catch { /* endpoint optional */ }
    })();
    return () => { alive = false; };
  }, []);

  return (
    <div style={{ height: "100%", overflow: "auto", padding: "8px 12px", fontFamily: t.mono,
      fontSize: 12, color: t.textDim, background: t.bg }}>
      {log.map((l, i) => <div key={i} style={{ whiteSpace: "pre-wrap" }}>{l}</div>)}
    </div>
  );
}
