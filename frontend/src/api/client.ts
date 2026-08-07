// Typed API client for the Imperium backend — covers the full surface the IDE binds to.
import { supabase } from "../lib/supabase";

export type Category = "security" | "performance" | "modernization" | "integration" | "documentation";
export type GateDecision = "approve" | "reject" | "defer";
export interface Vote { category: Category; decision: GateDecision; note?: string }

export interface Finding {
  category: Category; title: string; detail: string; confidence: number; locations: string[];
}
export interface AnalysisResponse {
  repository_id: string; status: string;
  structure_map: { nodes: unknown[]; edges: unknown[] } | null; findings: Finding[];
}
export interface Repo { id: string; url: string | null; ref: string; languages: string[]; created_at: string | null }
export interface GraphNode { id: string; name?: string; kind?: string; [k: string]: unknown }
export interface GraphEdge { source: string; target: string; type: string; method?: string; route?: string; label?: string }
export interface Simulation { file_path: string; confidence_score: number; safety_passed: boolean; blocked: boolean; diff: string }
export interface Rule { id?: string; statement: string; confidence: number; verified?: boolean; hitl_question?: string }
export interface Priority { file_path: string; score: number; [k: string]: unknown }
export interface Decision { category?: string; change_summary?: string; verdict?: string; approver?: string; gate?: string; created_at?: string; [k: string]: unknown }
export interface TimelineEvent { commit_sha: string; summary: string; author: string }
export interface Clarification { rule_id?: string; id?: string; statement?: string; hitl_question?: string; confidence?: number }
export interface FileNode { name: string; path: string; type: "file" | "dir"; children?: FileNode[] }

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}
async function get<T>(path: string): Promise<T> {
  return fetch(path, { headers: await authHeader() }).then(j<T>);
}
async function post<T>(path: string, body: unknown): Promise<T> {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeader()) },
    body: JSON.stringify(body),
  }).then(j<T>);
}
async function del<T>(path: string): Promise<T> {
  return fetch(path, { method: "DELETE", headers: await authHeader() }).then(j<T>);
}

/** Stream a POST SSE endpoint (chat), calling onChunk for each `data:` line. */
async function streamPost(path: string, body: unknown, onChunk: (s: string) => void, signal?: AbortSignal) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeader()) },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.body) return;
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const p of parts) {
      const line = p.replace(/^data:\s?/, "");
      if (line) onChunk(line);
    }
  }
}

/** Stream a GET SSE endpoint (run events), calling onEvent for each parsed JSON event. */
async function streamGet(path: string, onEvent: (e: Record<string, unknown>) => void, signal?: AbortSignal) {
  const res = await fetch(path, { headers: await authHeader(), signal });
  if (!res.body) return;
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const p of parts) {
      const line = p.replace(/^data:\s?/, "");
      if (!line) continue;
      try { onEvent(JSON.parse(line)); } catch { onEvent({ raw: line }); }
    }
  }
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  usage: () => get<Record<string, unknown>>("/api/usage"),

  listRepos: () => get<{ repositories: Repo[] }>("/api/repositories"),
  ingest: (repo_url: string, ref = "HEAD") =>
    post<{ repository_id: string; languages: string[] }>("/api/ingest", { repo_url, ref }),

  analysis: (id: string) => get<AnalysisResponse>(`/api/analysis/${id}`),
  runAnalysis: (id: string) => post<AnalysisResponse>(`/api/analysis/${id}`, {}),
  graph: (id: string, layer = "all") =>
    get<{ nodes: GraphNode[]; edges: GraphEdge[] }>(`/api/graph/${id}?layer=${layer}`),
  blast: (id: string, nodeId: string) => get<{ nodes: GraphNode[] }>(`/api/graph/${id}/blast/${nodeId}`),
  hierarchy: (id: string) => get<Record<string, unknown>>(`/api/hierarchy/${id}`),
  businessRules: (id: string) => get<{ rules?: Rule[]; business_rules?: Rule[] }>(`/api/business-rules/${id}`),
  priorities: (id: string) => get<{ priorities: Priority[] }>(`/api/priorities/${id}`),
  changesets: (id: string) => get<{ changesets: { id: string; name: string; status: string; files: string[] }[] }>(`/api/changesets/${id}`),
  simulations: (id: string) => get<{ simulations: Simulation[] }>(`/api/simulations/${id}`),
  timeline: (id: string) => get<{ events: TimelineEvent[] }>(`/api/timeline/${id}`),

  gateA: (repository_id: string, votes: Vote[]) => post(`/api/gate-a`, { repository_id, votes }),
  gateB: (repository_id: string, votes: Vote[]) => post(`/api/gate-b`, { repository_id, votes }),

  clarifications: (id: string) => get<{ questions: Clarification[] }>(`/api/clarifications/${id}`),
  answerClarification: (id: string, rule_id: string, answer: string) =>
    post(`/api/clarifications/${id}/answer`, { rule_id, answer }),

  decisions: (id: string) => get<{ decisions: Decision[] }>(`/api/decisions/${id}`),

  comprehension: (id: string) => get<Record<string, unknown>>(`/api/comprehension/${id}`),
  answerComprehension: (id: string, module_path: string, comprehension_score: number) =>
    post(`/api/comprehension/${id}/answer`, { module_path, comprehension_score }),

  chat: (id: string, query: string, onChunk: (s: string) => void, signal?: AbortSignal) =>
    streamPost(`/api/chat/${id}`, { query, top_k: 8 }, (line) => {
      // The backend streams JSON envelopes: {type:"token",text}, {type:"sources"},
      // {type:"error",message}, {type:"done"}. Unwrap them so only prose reaches the bubble.
      let ev: { type?: string; text?: string; message?: string };
      try { ev = JSON.parse(line); } catch { return; }
      if (ev.type === "token" && typeof ev.text === "string") onChunk(ev.text);
      else if (ev.type === "error") onChunk(`⚠ ${ev.message ?? "chat failed"}`);
    }, signal),

  fileTree: (id: string) => get<{ repository_id: string; root: string; tree: FileNode[] }>(`/api/files/${id}/tree`),
  fileContent: (id: string, path: string) =>
    get<{ path: string; size: number; binary: boolean; content: string }>(
      `/api/files/${id}/content?path=${encodeURIComponent(path)}`,
    ),

  startRun: (repository_id: string, repo_path = "") => post<{ run_id: string; status: string }>(`/api/runs`, { repository_id, repo_path }),
  getRun: (runId: string) => get<Record<string, unknown>>(`/api/runs/${runId}`),
  resumeRun: (runId: string, votes: Record<string, GateDecision>) => post(`/api/runs/${runId}/resume`, { votes }),
  deleteRun: (runId: string) => del(`/api/runs/${runId}`),
  runEvents: (runId: string, onEvent: (e: Record<string, unknown>) => void, signal?: AbortSignal) =>
    streamGet(`/api/runs/${runId}/events`, onEvent, signal),
};
