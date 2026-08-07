// Full-screen architecture/flow map: component cards laid out in kind-columns,
// arrows labeled with the API method → route that connects them.
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

export default function ArchitectureMap({ repoId }: { repoId: string }) {
  const { openFile } = useWorkbench();
  const ov = useMemo(() => overridesFor(repoId), [repoId]);

  // Merge the API layer (arrows we label) with the arch layer (component/page nodes).
  const { data, loading, error } = useAsync(async () => {
    const [apiL, archL] = await Promise.all([
      api.graph(repoId, "api"),
      api.graph(repoId, "arch"),
    ]);
    const nodeById = new Map<string, GraphNode>();
    for (const n of [...archL.nodes, ...apiL.nodes]) nodeById.set(n.id, n);
    return { nodes: [...nodeById.values()], edges: [...apiL.edges, ...archL.edges] };
  }, [repoId]);

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

  if (loading && !data) return <Center>Loading architecture map…</Center>;
  if (error) return <Center color={t.red}>Error: {error}</Center>;
  if (!nodes.length) return <Center>No graph data for this repository yet.</Center>;

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
