// GraphCanvas — renders a single graph layer as a React Flow diagram. Shared by
// the Module Map (`arch` layer: pages/components and their links) and the API Map
// (`api` layer: endpoint call arrows). Keeps layout + click-to-open in one place
// so the two map tabs don't duplicate rendering logic.
import { useMemo } from "react";
import ReactFlow, { Background, Controls, type Node, type Edge } from "reactflow";
import "reactflow/dist/style.css";
import { useAsync } from "../../hooks";
import { api, type GraphNode } from "../../api/client";
import { overridesFor } from "../../lib/graphOverrides";
import { layoutNodes, edgeLabel, groupOf } from "../../lib/graphLayout";
import { useWorkbench } from "../../context/WorkbenchContext";
import { t } from "../../theme";

const GROUP_ICON: Record<string, string> = { page: "▧", component: "◻", api: "◈", data: "▤", other: "•" };

export type GraphLayer = "arch" | "api";

const EMPTY_HINT: Record<GraphLayer, string> = {
  arch: "No module/page structure for this repository yet.",
  api: "No API connections detected for this repository yet.",
};

export default function GraphCanvas({ repoId, layer }: { repoId: string; layer: GraphLayer }) {
  const { openFile } = useWorkbench();
  const ov = useMemo(() => overridesFor(repoId), [repoId]);

  const { data, loading, error } = useAsync(async () => {
    const g = await api.graph(repoId, layer);
    // De-dupe nodes by id (defensive; a layer can reference a node twice).
    const nodeById = new Map<string, GraphNode>();
    for (const n of g.nodes) nodeById.set(n.id, n);
    return { nodes: [...nodeById.values()], edges: g.edges };
  }, [repoId, layer]);

  const pos = useMemo(() => (data ? layoutNodes(data.nodes, ov) : {}), [data, ov]);

  const nodes: Node[] = useMemo(
    () =>
      (data?.nodes ?? []).map((n) => {
        const o = ov.nodes?.[n.id];
        const g = groupOf(n, o);
        return {
          id: n.id,
          position: pos[n.id] ?? { x: 0, y: 0 },
          data: { label: `${GROUP_ICON[g]}  ${o?.name ?? n.name ?? n.id}`, path: (n as { path?: string }).path },
          style: {
            background: t.bgElev, color: t.text, border: `1px solid ${t.border}`,
            borderRadius: 8, fontSize: 12, fontFamily: t.sans, padding: "8px 10px", minWidth: 150,
          },
        };
      }),
    [data, pos, ov],
  );

  const edges: Edge[] = useMemo(
    () =>
      (data?.edges ?? []).map((e, i) => {
        const label = edgeLabel(e, ov.edges?.[`${e.source}->${e.target}`]);
        return {
          id: `${e.source}-${e.target}-${i}`,
          source: e.source, target: e.target, label,
          labelShowBg: true,
          style: { stroke: t.border },
          labelStyle: { fill: t.text, fontSize: 10, fontFamily: t.mono },
          labelBgStyle: { fill: t.bg },
        };
      }),
    [data, ov],
  );

  if (loading && !data) return <Center>Loading {layer === "api" ? "API map" : "module map"}…</Center>;
  if (error) return <Center color={t.red}>Error: {error}</Center>;
  if (!nodes.length) return <Center>{EMPTY_HINT[layer]}</Center>;

  return (
    <div style={{ width: "100%", height: "100%", background: t.bg }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        onNodeClick={(_, node) => {
          const p = (node.data as { path?: string }).path;
          if (p) openFile({ repoId, path: p, name: p.split("/").pop() ?? p });
        }}
      >
        <Background color={t.border} gap={18} />
        <Controls />
      </ReactFlow>
    </div>
  );
}

function Center({ children, color = t.textDim }: { children: React.ReactNode; color?: string }) {
  return <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color, fontSize: 13 }}>{children}</div>;
}
