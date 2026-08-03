// Thin API client for the Imperium backend. Foundation: typed calls to the spine.
import { supabase } from "../lib/supabase";

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

/** Returns Authorization header with the current Supabase session JWT, or empty. */
async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function get<T>(path: string): Promise<T> {
  const headers = await authHeader();
  return fetch(path, { headers }).then(json<T>);
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const headers = await authHeader();
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  }).then(json<T>);
}

export const api = {
  health: () => get<{ status: string }>("/health"),

  ingest: (repo_url: string, ref = "HEAD") =>
    post<{ repository_id: string; languages: string[]; status: string }>("/api/ingest", { repo_url, ref }),

  analysis: (repositoryId: string) =>
    get<AnalysisResponse>(`/api/analysis/${repositoryId}`),

  gateA: (repository_id: string, votes: { category: Category; decision: GateDecision; note?: string }[]) =>
    post("/api/gate-a", { repository_id, votes }),

  gateB: (repository_id: string, votes: { category: Category; decision: GateDecision; note?: string }[]) =>
    post("/api/gate-b", { repository_id, votes }),
};
