// Pure, DOM-free helpers that turn analyzed graph data + curated overrides into
// positions and edge labels. Unit-testable in isolation.
import type { GraphNode, GraphEdge } from "../api/client";
import type { Group, NodeOverride, RepoOverrides } from "./graphOverrides";

const COLUMN: Record<Group, number> = { page: 0, component: 1, api: 2, data: 3, other: 4 };
const COL_W = 260;
const ROW_H = 110;

/** Resolve a node's group: explicit override wins, else inferred from kind. */
export function groupOf(node: GraphNode, ov?: NodeOverride): Group {
  if (ov?.group) return ov.group;
  const k = (node.kind ?? "").toLowerCase();
  if (k.includes("page") || k.includes("route") || k.includes("view")) return "page";
  if (k.includes("component") || k.includes("module") || k.includes("file")) return "component";
  if (k.includes("endpoint") || k.includes("api")) return "api";
  if (k.includes("table") || k.includes("db") || k.includes("store")) return "data";
  return "other";
}

/** Arrow label: pinned override, else `method → route`, else route/method/type. */
export function edgeLabel(edge: GraphEdge, ov?: string): string {
  if (ov) return ov;
  if (edge.label) return edge.label;
  if (edge.method && edge.route) return `${edge.method} → ${edge.route}`;
  return edge.route ?? edge.method ?? edge.type;
}

/** Position map keyed by node id: kind-columns, stacked vertically; override wins. */
export function layoutNodes(nodes: GraphNode[], ov: RepoOverrides): Record<string, { x: number; y: number }> {
  const rowByCol: Record<number, number> = {};
  const pos: Record<string, { x: number; y: number }> = {};
  for (const n of nodes) {
    const o = ov.nodes?.[n.id];
    if (o?.position) { pos[n.id] = o.position; continue; }
    const col = COLUMN[groupOf(n, o)];
    const row = rowByCol[col] ?? 0;
    rowByCol[col] = row + 1;
    pos[n.id] = { x: col * COL_W, y: row * ROW_H };
  }
  return pos;
}
