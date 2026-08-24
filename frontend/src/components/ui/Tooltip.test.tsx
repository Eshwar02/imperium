import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Tooltip from "./Tooltip";

describe("Tooltip", () => {
  it("shows the label on hover and hides on leave", async () => {
    render(<Tooltip label="Explorer" delay={0}><button>icon</button></Tooltip>);
    const btn = screen.getByText("icon");
    await userEvent.hover(btn);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Explorer");
    await userEvent.unhover(btn);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});
