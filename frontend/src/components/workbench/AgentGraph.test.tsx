import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../../api/client", () => ({
  api: { runGraph: vi.fn() },
}));

import { api } from "../../api/client";
import { AgentGraphMini } from "./AgentGraph";

const mockApi = api as unknown as { runGraph: ReturnType<typeof vi.fn> };

const GRAPH = {
  run_id: "run1",
  status: "running",
  stage: "analyze",
  nodes: [
    { id: "run", label: "Orchestrator", type: "run", parent: null, status: "active" },
    { id: "build_kb", label: "Build Knowledge Base", type: "stage", parent: "run", status: "done" },
    { id: "analyze", label: "Analyze", type: "stage", parent: "run", status: "active" },
    { id: "analyze.structure", label: "Structure", type: "agent", parent: "analyze", status: "done" },
  ],
  edges: [],
};

describe("AgentGraphMini", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.runGraph.mockResolvedValue(GRAPH);
  });

  it("prompts to start a run when there is no active run", () => {
    render(<AgentGraphMini runId={null} />);
    expect(screen.getByText(/Start a run/i)).toBeInTheDocument();
    expect(mockApi.runGraph).not.toHaveBeenCalled();
  });

  it("renders the orchestrator, stages, and sub-agents for a live run", async () => {
    render(<AgentGraphMini runId="run1" />);
    expect(await screen.findByText("Orchestrator")).toBeInTheDocument();
    expect(screen.getByText("Analyze")).toBeInTheDocument();
    expect(screen.getByText("Structure")).toBeInTheDocument();
  });
});
