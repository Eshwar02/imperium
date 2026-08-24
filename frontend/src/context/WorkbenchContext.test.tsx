import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkbenchProvider, useWorkbench } from "./WorkbenchContext";

// Small harness that drives the editor operations and shows the resulting state.
function Harness() {
  const wb = useWorkbench();
  const open = (p: string) => wb.openFile({ repoId: "r1", path: p, name: p });
  return (
    <div>
      <button onClick={() => open("a.ts")}>open-a</button>
      <button onClick={() => open("b.ts")}>open-b</button>
      <button onClick={() => open("c.ts")}>open-c</button>
      <button onClick={() => wb.closeFile("b.ts")}>close-b</button>
      <button onClick={() => wb.closeOthers("b.ts")}>others-b</button>
      <button onClick={() => wb.closeAll()}>close-all</button>
      <div data-testid="tabs">{wb.editors.map((e) => e.path).join(",")}</div>
      <div data-testid="active">{wb.activePath ?? "none"}</div>
    </div>
  );
}

const tabs = () => screen.getByTestId("tabs").textContent;
const active = () => screen.getByTestId("active").textContent;

describe("WorkbenchContext editor operations", () => {
  it("opens files, dedupes, and tracks the active tab", async () => {
    render(<WorkbenchProvider><Harness /></WorkbenchProvider>);
    await userEvent.click(screen.getByText("open-a"));
    await userEvent.click(screen.getByText("open-b"));
    await userEvent.click(screen.getByText("open-a")); // duplicate — no new tab
    expect(tabs()).toBe("a.ts,b.ts");
    expect(active()).toBe("a.ts");
  });

  it("closing the active tab falls back to a neighbour", async () => {
    render(<WorkbenchProvider><Harness /></WorkbenchProvider>);
    await userEvent.click(screen.getByText("open-a"));
    await userEvent.click(screen.getByText("open-b"));
    await userEvent.click(screen.getByText("open-c")); // active = c
    await userEvent.click(screen.getByText("open-b")); // active = b
    await userEvent.click(screen.getByText("close-b"));
    expect(tabs()).toBe("a.ts,c.ts");
    expect(active()).toBe("c.ts"); // neighbour at the same index
  });

  it("closeOthers keeps only the target and makes it active", async () => {
    render(<WorkbenchProvider><Harness /></WorkbenchProvider>);
    await userEvent.click(screen.getByText("open-a"));
    await userEvent.click(screen.getByText("open-b"));
    await userEvent.click(screen.getByText("open-c"));
    await userEvent.click(screen.getByText("others-b"));
    expect(tabs()).toBe("b.ts");
    expect(active()).toBe("b.ts");
  });

  it("closeAll empties the group and clears the active tab", async () => {
    render(<WorkbenchProvider><Harness /></WorkbenchProvider>);
    await userEvent.click(screen.getByText("open-a"));
    await userEvent.click(screen.getByText("open-b"));
    await userEvent.click(screen.getByText("close-all"));
    expect(tabs()).toBe("");
    expect(active()).toBe("none");
  });
});
