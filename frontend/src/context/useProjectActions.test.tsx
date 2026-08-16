import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

// Mock the API client before importing anything that uses it.
vi.mock("../api/client", () => ({
  api: {
    listRepos: vi.fn(),
    ingest: vi.fn(),
  },
}));

import { api } from "../api/client";
import { RepoProvider } from "./RepoContext";
import { useProjectActions } from "./useProjectActions";

const mockApi = api as unknown as {
  listRepos: ReturnType<typeof vi.fn>;
  ingest: ReturnType<typeof vi.fn>;
};

const wrapper = ({ children }: { children: ReactNode }) => <RepoProvider>{children}</RepoProvider>;

describe("useProjectActions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.listRepos.mockResolvedValue({ repositories: [] });
  });

  it("ingests a URL, reloads repos, and makes the new repo active", async () => {
    mockApi.ingest.mockResolvedValue({ repository_id: "repo-new", languages: ["python"] });
    // First reload (mount) empty; after ingest, the new repo shows up.
    mockApi.listRepos
      .mockResolvedValueOnce({ repositories: [] })
      .mockResolvedValue({ repositories: [{ id: "repo-new", url: "https://x/y.git", ref: "HEAD", languages: ["python"], created_at: null }] });

    const { result } = renderHook(() => useProjectActions(), { wrapper });

    await act(async () => { await result.current.ingest("  https://x/y.git  "); });

    expect(mockApi.ingest).toHaveBeenCalledWith("https://x/y.git");
    await waitFor(() => expect(result.current.activeId).toBe("repo-new"));
    expect(result.current.error).toBeNull();
    expect(result.current.ingesting).toBe(false);
  });

  it("surfaces an error and rethrows when ingest fails", async () => {
    mockApi.ingest.mockRejectedValue(new Error("bad url"));
    const { result } = renderHook(() => useProjectActions(), { wrapper });

    await act(async () => {
      await expect(result.current.ingest("https://x/y.git")).rejects.toThrow("bad url");
    });

    await waitFor(() => expect(result.current.error).toBe("bad url"));
    expect(result.current.ingesting).toBe(false);
  });

  it("ignores empty input", async () => {
    const { result } = renderHook(() => useProjectActions(), { wrapper });
    await act(async () => { await result.current.ingest("   "); });
    expect(mockApi.ingest).not.toHaveBeenCalled();
  });
});
