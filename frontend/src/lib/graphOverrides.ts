// Curated layer over the analyzed graph: rename/group nodes, pin arrow labels
// and positions. Keyed by repository id, with "*" applied to every repo.
export type Group = "page" | "component" | "api" | "data" | "other";

export interface NodeOverride { name?: string; group?: Group; position?: { x: number; y: number } }
export interface RepoOverrides {
  nodes?: Record<string, NodeOverride>;
  edges?: Record<string, string>; // "source->target" -> label
}

const OVERRIDES: Record<string, RepoOverrides> = {
  "*": {},
};

export function overridesFor(repoId: string): RepoOverrides {
  const base = OVERRIDES["*"] ?? {};
  const repo = OVERRIDES[repoId] ?? {};
  return {
    nodes: { ...(base.nodes ?? {}), ...(repo.nodes ?? {}) },
    edges: { ...(base.edges ?? {}), ...(repo.edges ?? {}) },
  };
}
