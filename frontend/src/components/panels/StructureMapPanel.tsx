// Structure map — renders the repo dependency graph via reactflow, with blast-radius on click.
import { useMemo, useState } from "react";
import ReactFlow, { Background, Controls, type Node, type Edge } from "reactflow";
import "reactflow/dist/style.css";
import { PanelShell, Empty, Btn } from "../ui";
import { useAsync } from "../../hooks";
import { useRepo } from "../../context/RepoContext";
import { api } from "../../api/client";
import { t } from "../../theme";

export default function StructureMapPanel() {
  const { activeId } = useRepo();
  const [blast, setBlast] = useState<{ nodeId: string; count: number } | null>(null);

  const { data, loading, error, reload } = useAsync(
    () => (activeId ? api.graph(activeId) : Promise.resolve({ nodes: [], edges: [] })),
    [activeId],
  );

  const nodes: Node[] = useMemo(
    () =>
      (data?.nodes ?? []).map((n, i) => ({
        id: n.id,
        data: { label: n.name || n.id },
        position: { x: (i % 6) * 180, y: Math.floor(i / 6) * 110 },
        style: {
          background: t.bgElev,
          color: t.text,
          border: `1px solid ${t.border}`,
          borderRadius: 6,
          fontSize: 12,
          fontFamily: t.sans,
          padding: 6,
        },
      })),
    [data],
  );

  const edges: Edge[] = useMemo(
    () =>
      (data?.edges ?? []).map((e) => ({
        id: `${e.source}-${e.target}-${e.type}`,
        source: e.source,
        target: e.target,
        label: e.type,
        style: { stroke: t.border },
        labelStyle: { fill: t.textDim, fontSize: 10, fontFamily: t.mono },
      })),
    [data],
  );

  if (!activeId)
    return (
      <PanelShell title="Structure Map">
        <Empty>Select a repository</Empty>
      </PanelShell>
    );

  const onNodeClick = async (nodeId: string) => {
    try {
      const res = await api.blast(activeId, nodeId);
      setBlast({ nodeId, count: res.nodes.length });
    } catch {
      setBlast(null);
    }
  };

  return (
    <PanelShell
      title="Structure Map"
      right={<Btn onClick={reload} disabled={loading}>↻</Btn>}
    >
      {error ? (
        <Empty>Error: {error}</Empty>
      ) : loading && !data ? (
        <Empty>Loading…</Empty>
      ) : nodes.length === 0 ? (
        <Empty>No graph nodes</Empty>
      ) : (
        <div style={{ position: "relative", width: "100%", height: "100%", background: t.bg }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            onNodeClick={(_, node) => onNodeClick(node.id)}
          >
            <Background color={t.border} gap={18} />
            <Controls />
          </ReactFlow>
          {blast && (
            <div
              style={{
                position: "absolute",
                top: 10,
                right: 10,
                zIndex: 10,
                background: t.bgElev,
                border: `1px solid ${t.border}`,
                borderRadius: 6,
                padding: "6px 10px",
                fontSize: 12,
                color: t.text,
                fontFamily: t.sans,
              }}
            >
              <span style={{ color: t.accent, fontWeight: 700 }}>{blast.count}</span> dependents
              <div style={{ color: t.textDim, fontSize: 10, fontFamily: t.mono }}>{blast.nodeId}</div>
            </div>
          )}
        </div>
      )}
    </PanelShell>
  );
}
