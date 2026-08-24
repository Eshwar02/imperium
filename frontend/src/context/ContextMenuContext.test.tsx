import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ContextMenuProvider, useContextMenu, type MenuEntry } from "./ContextMenuContext";

function Harness({ items }: { items: MenuEntry[] }) {
  const menu = useContextMenu();
  return <div data-testid="target" onContextMenu={(e) => menu.open(e, items)}>right-click me</div>;
}

describe("ContextMenu", () => {
  it("opens at the cursor and fires the chosen action", async () => {
    const onClick = vi.fn();
    render(
      <ContextMenuProvider>
        <Harness items={[{ label: "Do Thing", onClick }]} />
      </ContextMenuProvider>,
    );

    await userEvent.pointer({ keys: "[MouseRight]", target: screen.getByTestId("target") });
    const item = await screen.findByText("Do Thing");
    await userEvent.click(item);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("does not fire disabled entries", async () => {
    const onClick = vi.fn();
    render(
      <ContextMenuProvider>
        <Harness items={[{ label: "Nope", onClick, disabled: true }]} />
      </ContextMenuProvider>,
    );
    await userEvent.pointer({ keys: "[MouseRight]", target: screen.getByTestId("target") });
    await userEvent.click(await screen.findByText("Nope"));
    expect(onClick).not.toHaveBeenCalled();
  });
});
