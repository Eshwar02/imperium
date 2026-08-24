import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NotificationProvider, useNotifications } from "./NotificationContext";

function Harness() {
  const n = useNotifications();
  return (
    <button onClick={() => n.error("Boom happened", { timeout: null, actions: [{ label: "Retry", onClick: () => n.success("Retried") }] })}>
      go
    </button>
  );
}

describe("Notifications", () => {
  it("shows a toast and dismisses it", async () => {
    render(<NotificationProvider><Harness /></NotificationProvider>);
    await userEvent.click(screen.getByText("go"));
    expect(await screen.findByText("Boom happened")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/Dismiss notification/i));
    expect(screen.queryByText("Boom happened")).not.toBeInTheDocument();
  });

  it("runs an action button", async () => {
    render(<NotificationProvider><Harness /></NotificationProvider>);
    await userEvent.click(screen.getByText("go"));
    await userEvent.click(await screen.findByText("Retry"));
    expect(await screen.findByText("Retried")).toBeInTheDocument();
  });
});
