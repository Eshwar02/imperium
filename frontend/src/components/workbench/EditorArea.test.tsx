import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";

// Monaco is heavy and DOM-driven — stub it with a plain element that shows the value.
vi.mock("@monaco-editor/react", () => ({
  default: ({ value }: { value: string }) => <div data-testid="monaco">{value}</div>,
}));

vi.mock("../../api/client", () => ({
  api: {
    listRepos: vi.fn().mockResolvedValue({ repositories: [] }),
    fileContent: vi.fn().mockResolvedValue({ content: "hello world", binary: false }),
  },
}));

import { ThemeProvider } from "../../context/ThemeContext";
import { RepoProvider } from "../../context/RepoContext";
import { WorkbenchProvider, useWorkbench } from "../../context/WorkbenchContext";
import { ContextMenuProvider } from "../../context/ContextMenuContext";
import EditorArea from "./EditorArea";

// Opens two files on mount so EditorArea renders a tab strip.
function Seed({ children }: { children: ReactNode }) {
  const wb = useWorkbench();
  return (
    <>
      <button onClick={() => wb.openFile({ repoId: "r1", path: "src/a.ts", name: "a.ts" })}>open-a</button>
      <button onClick={() => wb.openFile({ repoId: "r1", path: "src/b.ts", name: "b.ts" })}>open-b</button>
      {children}
    </>
  );
}

const wrap = (ui: ReactNode) => (
  <ThemeProvider><RepoProvider><WorkbenchProvider><ContextMenuProvider>
    <Seed>{ui}</Seed>
  </ContextMenuProvider></WorkbenchProvider></RepoProvider></ThemeProvider>
);

describe("EditorArea tabs", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a tab per open file and loads content in Monaco", async () => {
    render(wrap(<EditorArea />));
    await userEvent.click(screen.getByText("open-a"));
    // Name shows in the tab (and again in the breadcrumb).
    expect(screen.getAllByText("a.ts").length).toBeGreaterThan(0);
    expect(await screen.findByTestId("monaco")).toHaveTextContent("hello world");
  });

  it("right-clicking a tab offers close actions and Close removes it", async () => {
    render(wrap(<EditorArea />));
    await userEvent.click(screen.getByText("open-a"));
    await userEvent.click(screen.getByText("open-b"));

    // Right-click the first tab (index 0 is the tab; later matches are breadcrumbs).
    await userEvent.pointer({ keys: "[MouseRight]", target: screen.getAllByText("a.ts")[0] });

    expect(await screen.findByText("Close Others")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Close"));

    await waitFor(() => expect(screen.queryByText("a.ts")).not.toBeInTheDocument());
    expect(screen.getAllByText("b.ts").length).toBeGreaterThan(0);
  });
});
