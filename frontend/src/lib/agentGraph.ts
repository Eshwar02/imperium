// Pure helpers for the live Agent Graph — kept free of React/React Flow so they
// can be unit-tested in isolation (see agentGraph.test.ts).
import { t } from "../theme";
import type { AgentNodeStatus } from "../api/client";

export interface NodeStyle {
  color: string;   // accent/status color (border + icon)
  icon: string;    // status glyph
  pulse: boolean;  // animate to signal live work
  label: string;   // human-readable status word
}

/** Map an agent-node status to its visual treatment. */
export function agentNodeStyle(status: AgentNodeStatus): NodeStyle {
  switch (status) {
    case "active":
      return { color: t.accent, icon: "●", pulse: true, label: "active" };
    case "done":
      return { color: t.green, icon: "✓", pulse: false, label: "done" };
    case "awaiting":
      return { color: t.yellow, icon: "⏸", pulse: false, label: "awaiting" };
    case "failed":
      return { color: t.red, icon: "✕", pulse: false, label: "failed" };
    case "idle":
    default:
      return { color: t.textDim, icon: "○", pulse: false, label: "idle" };
  }
}

/** True while a run is still doing work (used to decide whether to keep polling). */
export function isRunLive(status: string | undefined): boolean {
  const s = (status ?? "").toLowerCase();
  return !(s.includes("complete") || s.includes("fail") || s.includes("cancel"));
}

/**
 * Turn a raw run event into a single readable line for the activity feed.
 * Falls back to a compact key summary for events we don't specially format.
 */
export function formatEvent(e: Record<string, unknown>): string {
  const s = (k: string) => (typeof e[k] === "string" ? (e[k] as string) : undefined);
  const ev = s("event");
  const agent = s("agent");

  if (ev === "agent_start" && agent) return `▸ ${titleize(agent)} agent started`;
  if (ev === "agent_done" && agent) {
    const n = typeof e.findings === "number" ? e.findings : undefined;
    return `✓ ${titleize(agent)} agent finished${n != null ? ` — ${n} finding${n === 1 ? "" : "s"}` : ""}`;
  }
  if (ev === "agent_error" && agent) return `✕ ${titleize(agent)} agent failed${s("error") ? ` — ${s("error")}` : ""}`;

  const node = s("node");
  if (node) return `● Stage complete: ${titleize(node)}`;

  const status = s("status");
  if (status) return `Run status: ${status}`;

  // Fallback: compact, human-ish key summary rather than raw JSON.
  const keys = Object.keys(e).filter((k) => e[k] != null);
  if (keys.length === 0) return "(empty event)";
  return keys.map((k) => `${k}=${String(e[k])}`).join("  ");
}

function titleize(id: string): string {
  return id.replace(/[_.]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
