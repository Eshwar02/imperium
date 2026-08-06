// Terminal — a small read-eval loop over the Imperium API (not a real shell).
import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { useRepo } from "../../context/RepoContext";
import { t } from "../../theme";

const HELP = [
  "imperium terminal — commands:",
  "  help              show this help",
  "  health            backend liveness",
  "  services          postgres / qdrant / neo4j / redis status",
  "  repos             list your repositories",
  "  clear             clear the terminal",
].join("\n");

export default function Terminal() {
  const { repos } = useRepo();
  const [lines, setLines] = useState<string[]>(["Imperium Terminal. Type 'help'."]);
  const [cmd, setCmd] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => { endRef.current?.scrollIntoView(); }, [lines]);

  const push = (s: string) => setLines((l) => [...l, s]);

  async function run(raw: string) {
    const c = raw.trim();
    push(`$ ${c}`);
    if (c === "clear") { setLines([]); return; }
    if (c === "help" || c === "") { push(HELP); return; }
    if (c === "health") {
      try { const r = await api.health(); push(JSON.stringify(r)); }
      catch (e) { push(`error: ${String((e as Error).message)}`); }
      return;
    }
    if (c === "services") {
      try {
        const r = await fetch("/health/services").then((x) => x.json());
        push(JSON.stringify(r, null, 2));
      } catch (e) { push(`error: ${String((e as Error).message)}`); }
      return;
    }
    if (c === "repos") {
      if (repos.length === 0) push("(no repositories)");
      repos.forEach((r) => push(`${r.id}  ${r.url ?? ""}`));
      return;
    }
    push(`command not found: ${c}`);
  }

  return (
    <div style={{ height: "100%", overflow: "auto", padding: "8px 12px", fontFamily: t.mono,
      fontSize: 12, color: t.text, background: t.bg }}
      onClick={(e) => (e.currentTarget.querySelector("input") as HTMLInputElement)?.focus()}>
      {lines.map((l, i) => <div key={i} style={{ whiteSpace: "pre-wrap" }}>{l}</div>)}
      <div style={{ display: "flex", gap: 6 }}>
        <span style={{ color: t.green }}>$</span>
        <input value={cmd} autoFocus
          onChange={(e) => setCmd(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { run(cmd); setCmd(""); } }}
          style={{ flex: 1, background: "transparent", border: "none", outline: "none",
            color: t.text, fontFamily: t.mono, fontSize: 12 }} />
      </div>
      <div ref={endRef} />
    </div>
  );
}
