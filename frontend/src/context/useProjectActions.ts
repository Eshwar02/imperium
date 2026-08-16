// Shared project actions — the single source of truth for adding (ingesting) and
// switching projects, so the Projects panel, title bar, and command palette all
// stay in sync. Thin wrapper over RepoContext + api.ingest.
import { useCallback, useState } from "react";
import { api } from "../api/client";
import { useRepo } from "./RepoContext";

export interface ProjectActions {
  repos: ReturnType<typeof useRepo>["repos"];
  activeId: string | null;
  setActiveId: (id: string) => void;
  ingest: (url: string) => Promise<void>;
  ingesting: boolean;
  error: string | null;
}

export function useProjectActions(): ProjectActions {
  const { repos, activeId, setActiveId, reloadRepos } = useRepo();
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ingest = useCallback(
    async (url: string) => {
      const trimmed = url.trim();
      if (!trimmed || ingesting) return;
      setIngesting(true);
      setError(null);
      try {
        const { repository_id } = await api.ingest(trimmed);
        await reloadRepos();
        setActiveId(repository_id);
      } catch (e) {
        setError(String(e instanceof Error ? e.message : e));
        throw e;
      } finally {
        setIngesting(false);
      }
    },
    [ingesting, reloadRepos, setActiveId],
  );

  return { repos, activeId, setActiveId, ingest, ingesting, error };
}
