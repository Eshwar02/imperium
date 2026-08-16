import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("../../api/client", () => ({
  api: { graph: vi.fn() },
}));

// React Flow needs layout/resize APIs jsdom lacks; stub to a simple container that
// still renders node labels so we can assert on them.
vi.mock("reactflow", () => ({
  __esModule: true,
  default: ({ nodes }: { nodes: { id: string; data: { label: string } }[] }) => (
    <div data-testid="rf">{nodes.map((n) => <div key={n.id}>{n.data.label}</div>)}</div>
  ),
  Background: () => null,
  Controls: () => null,
  MarkerType: { ArrowClosed: "arrowclosed" },
}));

import { api } from "../../api/client";
import { WorkbenchProvider } from "../../context/WorkbenchContext";
import GraphCanvas from "./GraphCanvas";

const mockGraph = (api as unknown as { graph: ReturnType<typeof vi.fn> }).graph;

function renderCanvas(layer: "arch" | "api") {
  return render(
    <WorkbenchProvider>
      <GraphCanvas repoId="r1" layer={layer} />
    </WorkbenchProvider>,
  );
}

describe("GraphCanvas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGraph.mockResolvedValue({
      nodes: [{ id: "n1", name: "Dashboard" }],
      edges: [],
    });
  });

  it("requests the arch layer for the module map", async () => {
    renderCanvas("arch");
    await waitFor(() => expect(mockGraph).toHaveBeenCalledWith("r1", "arch"));
    expect(await screen.findByText(/Dashboard/)).toBeInTheDocument();
  });

  it("requests the api layer for the API map", async () => {
    renderCanvas("api");
    await waitFor(() => expect(mockGraph).toHaveBeenCalledWith("r1", "api"));
  });

  it("shows a layer-specific empty hint when there are no nodes", async () => {
    mockGraph.mockResolvedValue({ nodes: [], edges: [] });
    renderCanvas("api");
    expect(await screen.findByText(/No API connections/)).toBeInTheDocument();
  });
});
