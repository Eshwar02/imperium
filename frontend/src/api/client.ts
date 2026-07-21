// Thin API client for the Imperium backend. Foundation: typed calls to the spine.
// TODO(team): error handling, loading states, auth headers.

export type Category = "security" | "performance" | "modernization" | "integration" | "documentation";
export type GateDecision = "approve" | "reject" | "defer";

export interface Finding {
  category: Category;
  title: string;
  detail: string;
  confidence: number;
  locations: string[];
}

export interface AnalysisResponse {
  repository_id: string;
  status: string;
  structure_map: { nodes: unknown[]; edges: unknown[] } | null;
  findings: Finding[];
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/health").then(json<{ status: string }>),

  ingest: (repo_url: string, ref = "HEAD") =>
    fetch("/api/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url, ref }),
    }).then(json<{ repository_id: string; languages: string[]; status: string }>),

  analysis: (repositoryId: string) =>
    fetch(`/api/analysis/${repositoryId}`).then(json<AnalysisResponse>),

  gateA: (repository_id: string, votes: { category: Category; decision: GateDecision; note?: string }[]) =>
    fetch("/api/gate-a", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repository_id, votes }),
    }).then(json),

  gateB: (repository_id: string, votes: { category: Category; decision: GateDecision; note?: string }[]) =>
    fetch("/api/gate-b", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repository_id, votes }),
    }).then(json),
};
