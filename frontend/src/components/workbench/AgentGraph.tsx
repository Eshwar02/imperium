// Live Agent Graph — renders a run's multi-agent decomposition (Orchestrator →
// stages → sub-agents), lighting each node up idle/active/done/awaiting/failed in
// real time. Full React Flow view for the editor tab; a compact tree for the Run
// sidebar. Both share `useRunGraph`, which polls while the run is live.
import { useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, { Background, Controls, type Node, type Edge, MarkerType } from "reactflow";
import "reactflow/dist/style.css";
import { api, type AgentGraphData, type AgentNode } from "../../api/client";
import { agentNodeStyle, isRunLive } from "../../lib/agentGraph";
import { t } from "../../theme";

/** Poll the run's agent graph every ~1.5s while it is live. */
export function useRunGraph(runId: string | null): AgentGraphData | null {
  const [graph, setGraph] = useState<AgentGraphData | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    setGraph(null);
    if (!runId) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const g = await api.runGraph(runId);
        if (cancelled) return;
        setGraph(g);
        if (isRunLive(g.status)) timer.current = window.setTimeout(tick, 1500);
      } catch {
        if (!cancelled) timer.current = window.setTimeout(tick, 3000);
      }
    };
    tick();

    return () => {
      cancelled = true;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [runId]);

  return graph;
}

// ── layout ────────────────────────────────────────────────────────────────────
// Deterministic: Orchestrator on top, stages in a horizontal row, sub-agents
// stacked under their parent stage.

const STAGE_Y = 130;
const AGENT_Y0 = 270;
const COL_W = 190;
const AGENT_ROW_H = 64;

function layout(nodes: AgentNode[]): Record<string, { x: number; y: number }> {
  const stages = nodes.filter((n) => n.type === "stage" || n.type === "gate");
  const stageX: Record<string, number> = {};
  stages.forEach((n, i) => (stageX[n.id] = i * COL_W));
  const spanW = Math.max(0, (stages.length - 1) * COL_W);

  const pos: Record<string, { x: number; y: number }> = {};
  const agentCount: Record<string, number> = {};

  for (const n of nodes) {
    if (n.type === "run") {
      pos[n.id] = { x: spanW / 2, y: 0 };
    } else if (n.type === "stage" || n.type === "gate") {
      pos[n.id] = { x: stageX[n.id] ?? 0, y: STAGE_Y };
    } else if (n.type === "agent" && n.parent) {
      const i = agentCount[n.parent] ?? 0;
      agentCount[n.parent] = i + 1;
      pos[n.id] = { x: (stageX[n.parent] ?? 0) - 20, y: AGENT_Y0 + i * AGENT_ROW_H };
    } else {
      pos[n.id] = { x: 0, y: 0 };
    }
  }
  return pos;
}

// ── full React Flow view (editor tab) ──────────────────────────────────────────

export default function AgentGraph({ runId }: { runId: string | null }) {
  const graph = useRunGraph(runId);
  const pos = useMemo(() => (graph ? layout(graph.nodes) : {}), [graph]);

  const rfNodes: Node[] = useMemo(() => {
    if (!graph) return [];
    return graph.nodes.map((n) => {
      const st = agentNodeStyle(n.status);
      const isRun = n.type === "run";
      return {
        id: n.id,
        position: pos[n.id] ?? { x: 0, y: 0 },
        data: { label: `${st.icon}  ${n.label}${n.detail ? `\n${n.detail}` : ""}` },
        style: {
          background: isRun ? t.bgElev : t.bgPanel,
          color: t.text,
          border: `1px solid ${st.color}`,
          borderRadius: 8,
          fontSize: n.type === "agent" ? 11 : 12,
          fontFamily: t.sans,
          fontWeight: isRun ? 700 : 400,
          padding: "8px 10px",
          minWidth: n.type === "agent" ? 120 : 150,
          whiteSpace: "pre-wrap",
          boxShadow: st.pulse ? `0 0 0 2px ${st.color}55` : "none",
        },
      };
    });
  }, [graph, pos]);

  const rfEdges: Edge[] = useMemo(() => {
    if (!graph) return [];
    return graph.edges.map((e, i) => ({
      id: `${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      animated: e.kind === "next",
      style: { stroke: e.kind === "next" ? t.accent : t.border, strokeDasharray: e.kind === "contains" ? "4 3" : undefined },
      markerEnd: e.kind === "next" ? { type: MarkerType.ArrowClosed, color: t.accent } : undefined,
    }));
  }, [graph]);

  if (!runId) return <Center>No active run. Start a run to see the agent graph.</Center>;
  if (!graph) return <Center>Loading agent graph…</Center>;
  if (graph.nodes.length === 0) return <Center>No agent activity yet.</Center>;

  return (
    <div style={{ width: "100%", height: "100%", background: t.bg }}>
      <ReactFlow nodes={rfNodes} edges={rfEdges} fitView nodesDraggable={false} nodesConnectable={false}>
        <Background color={t.border} gap={18} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

// ── compact tree (Run sidebar) ──────────────────────────────────────────────────

export function AgentGraphMini({ runId }: { runId: string | null }) {
  const graph = useRunGraph(runId);
  if (!runId) return <Hint>Start a run to watch the agents.</Hint>;
  if (!graph || graph.nodes.length === 0) return <Hint>Waiting for agent activity…</Hint>;

  const stages = graph.nodes.filter((n) => n.type === "stage" || n.type === "gate");
  const agentsOf = (parent: string) => graph.nodes.filter((n) => n.type === "agent" && n.parent === parent);

  return (
    <div style={{ padding: "6px 10px", overflow: "auto" }}>
      <Line label="Orchestrator" status="run" detail={graph.stage} bold />
      {stages.map((n) => (
        <div key={n.id}>
          <Line label={n.label} status={n.status} indent={1} />
          {agentsOf(n.id).map((a) => (
            <Line key={a.id} label={a.label} status={a.status} indent={2} />
          ))}
        </div>
      ))}
    </div>
  );
}

function Line({ label, status, detail, indent = 0, bold }: {
  label: string; status: string; detail?: string; indent?: number; bold?: boolean;
}) {
  const st = status === "run"
    ? { color: t.text, icon: "◆", label: "" }
    : agentNodeStyle(status as never);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "2px 0", paddingLeft: indent * 14,
      fontSize: 12, color: bold ? t.text : t.textDim, fontFamily: t.sans }}>
      <span style={{ color: st.color, width: 12, textAlign: "center" }}>{st.icon}</span>
      <span style={{ fontWeight: bold ? 700 : 400, color: bold ? t.text : t.text }}>{label}</span>
      {detail && <span style={{ color: t.textDim, fontSize: 11 }}>· {detail}</span>}
    </div>
  );
}

function Center({ children, color = t.textDim }: { children: React.ReactNode; color?: string }) {
  return <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color, fontSize: 13 }}>{children}</div>;
}
function Hint({ children }: { children: React.ReactNode }) {
  return <div style={{ padding: 12, fontSize: 12, color: t.textDim }}>{children}</div>;
}
