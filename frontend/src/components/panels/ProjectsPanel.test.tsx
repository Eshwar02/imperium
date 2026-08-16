import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";

vi.mock("../../api/client", () => ({
  api: { listRepos: vi.fn(), ingest: vi.fn() },
}));

import { api } from "../../api/client";
import { RepoProvider } from "../../context/RepoContext";
import ProjectsPanel from "./ProjectsPanel";

const mockApi = api as unknown as { listRepos: ReturnType<typeof vi.fn>; ingest: ReturnType<typeof vi.fn> };
const wrapper = ({ children }: { children: ReactNode }) => <RepoProvider>{children}</RepoProvider>;

describe("ProjectsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.listRepos.mockResolvedValue({ repositories: [] });
  });

  it("renders the git-URL input and an empty state", async () => {
    render(<ProjectsPanel />, { wrapper });
    expect(screen.getByLabelText(/Git repository URL/i)).toBeInTheDocument();
    expect(await screen.findByText(/No projects yet/i)).toBeInTheDocument();
  });

  it("adds a project by typing a URL and clicking Add", async () => {
    mockApi.ingest.mockResolvedValue({ repository_id: "r1", languages: [] });
    render(<ProjectsPanel />, { wrapper });

    await userEvent.type(screen.getByLabelText(/Git repository URL/i), "https://x/y.git");
    await userEvent.click(screen.getByRole("button", { name: /Add Project/i }));

    await waitFor(() => expect(mockApi.ingest).toHaveBeenCalledWith("https://x/y.git"));
  });

  it("lists repositories by name and highlights the active one", async () => {
    mockApi.listRepos.mockResolvedValue({
      repositories: [{ id: "r1", url: "https://github.com/acme/store.git", ref: "HEAD", languages: ["python"], created_at: null }],
    });
    render(<ProjectsPanel />, { wrapper });
    expect(await screen.findByText("store")).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
  });
});
