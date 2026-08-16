import { describe, it, expect } from "vitest";
import { agentNodeStyle, isRunLive, formatEvent } from "./agentGraph";

describe("agentNodeStyle", () => {
  it("marks active nodes with a pulse", () => {
    const s = agentNodeStyle("active");
    expect(s.pulse).toBe(true);
    expect(s.label).toBe("active");
  });

  it("gives done/awaiting/failed distinct icons", () => {
    expect(agentNodeStyle("done").icon).toBe("✓");
    expect(agentNodeStyle("awaiting").icon).toBe("⏸");
    expect(agentNodeStyle("failed").icon).toBe("✕");
  });

  it("treats unknown/idle as non-pulsing idle", () => {
    expect(agentNodeStyle("idle").pulse).toBe(false);
    // @ts-expect-error — exercising the default branch defensively
    expect(agentNodeStyle("bogus").label).toBe("idle");
  });
});

describe("isRunLive", () => {
  it("is false for terminal statuses", () => {
    expect(isRunLive("complete")).toBe(false);
    expect(isRunLive("failed")).toBe(false);
    expect(isRunLive("cancelled")).toBe(false);
  });
  it("is true for running/awaiting/unknown", () => {
    expect(isRunLive("running")).toBe(true);
    expect(isRunLive("awaiting_gate")).toBe(true);
    expect(isRunLive(undefined)).toBe(true);
  });
});

describe("formatEvent", () => {
  it("formats agent lifecycle events with finding counts", () => {
    expect(formatEvent({ event: "agent_start", agent: "structure" })).toBe("▸ Structure agent started");
    expect(formatEvent({ event: "agent_done", agent: "security", findings: 1 })).toBe("✓ Security agent finished — 1 finding");
    expect(formatEvent({ event: "agent_done", agent: "security", findings: 3 })).toBe("✓ Security agent finished — 3 findings");
    expect(formatEvent({ event: "agent_error", agent: "research", error: "boom" })).toBe("✕ Research agent failed — boom");
  });

  it("formats stage completion and status", () => {
    expect(formatEvent({ node: "build_kb" })).toBe("● Stage complete: Build Kb");
    expect(formatEvent({ status: "awaiting_gate" })).toBe("Run status: awaiting_gate");
  });

  it("falls back to a compact key summary, never raw JSON braces", () => {
    const line = formatEvent({ foo: 1, bar: "x" });
    expect(line).toContain("foo=1");
    expect(line).toContain("bar=x");
    expect(line).not.toContain("{");
  });
});
