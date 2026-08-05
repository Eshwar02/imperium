// Chat — streaming Q&A grounded in the active repository.
import { useEffect, useRef, useState } from "react";
import { PanelShell, Empty, Btn } from "../ui";
import { useRepo } from "../../context/RepoContext";
import { api } from "../../api/client";
import { t } from "../../theme";

interface Msg { role: "user" | "assistant"; text: string }

export default function ChatPanel() {
  const { activeId } = useRepo();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  if (!activeId) return <PanelShell title="Chat"><Empty>Select a repository.</Empty></PanelShell>;

  async function send() {
    const q = input.trim();
    if (!q || busy || !activeId) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text: q }, { role: "assistant", text: "" }]);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await api.chat(activeId, q, (chunk) => {
        setMessages((m) => {
          const next = m.slice();
          const last = next[next.length - 1];
          if (last && last.role === "assistant") next[next.length - 1] = { ...last, text: last.text + chunk };
          return next;
        });
      }, ctrl.signal);
    } catch (e) {
      setMessages((m) => {
        const next = m.slice();
        const last = next[next.length - 1];
        if (last && last.role === "assistant" && !last.text) next[next.length - 1] = { ...last, text: `⚠ ${String((e as Error)?.message ?? e)}` };
        return next;
      });
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  return (
    <PanelShell title="Chat">
      <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
        <div ref={scrollRef} style={{ flex: 1, minHeight: 0, overflow: "auto", display: "flex", flexDirection: "column", gap: 8, paddingBottom: 8 }}>
          {messages.length === 0 && <Empty>Ask a question about this repository.</Empty>}
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                maxWidth: "88%",
                background: m.role === "assistant" ? t.bgElev : t.accent,
                color: m.role === "assistant" ? t.text : "#fff",
                border: `1px solid ${m.role === "assistant" ? t.border : "transparent"}`,
                borderRadius: 8, padding: "6px 10px", fontSize: 13, whiteSpace: "pre-wrap", wordBreak: "break-word",
                fontFamily: t.sans,
              }}
            >
              {m.text || (m.role === "assistant" && busy ? "…" : "")}
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8, borderTop: `1px solid ${t.border}`, paddingTop: 8, flexShrink: 0 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder="Ask about the repo…"
            style={{ flex: 1, background: t.bg, color: t.text, border: `1px solid ${t.border}`, borderRadius: 5, padding: "6px 10px", fontSize: 13, fontFamily: t.sans, outline: "none" }}
          />
          <Btn kind="primary" onClick={send} disabled={busy || !input.trim()}>{busy ? "…" : "Send"}</Btn>
        </div>
      </div>
    </PanelShell>
  );
}
