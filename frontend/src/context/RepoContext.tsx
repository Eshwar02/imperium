// Active-repository + run state shared across every panel.
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Repo } from "../api/client";

interface RepoCtx {
  repos: Repo[];
  activeId: string | null;
  setActiveId: (id: string) => void;
  reloadRepos: () => void;
  runId: string | null;
  setRunId: (id: string | null) => void;
}
const Ctx = createContext<RepoCtx | null>(null);

export function RepoProvider({ children }: { children: ReactNode }) {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  const reloadRepos = () =>
    api.listRepos().then((r) => {
      setRepos(r.repositories);
      setActiveId((cur) => cur ?? r.repositories[0]?.id ?? null);
    }).catch(() => undefined);

  useEffect(() => { reloadRepos(); }, []);

  return (
    <Ctx.Provider value={{ repos, activeId, setActiveId, reloadRepos, runId, setRunId }}>
      {children}
    </Ctx.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useRepo() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useRepo must be inside RepoProvider");
  return c;
}
