import ReactFlow, { Background, Controls, type Edge, type Node } from "reactflow";
import "reactflow/dist/style.css";

// Interactive Structure Map (PRD Step 3 / TDD §3). Node-based, movable, zoomable.
// Foundation: renders React Flow with placeholder nodes. Wire to
// api.analysis(repoId).structure_map when the Structure Agent produces it.
// TODO(team): fetch real {nodes, edges}; export as Mermaid diagram-as-code.

const placeholderNodes: Node[] = [
  { id: "app", position: { x: 250, y: 20 }, data: { label: "App (entrypoint)" }, type: "input" },
  { id: "api", position: { x: 100, y: 140 }, data: { label: "API layer" } },
  { id: "db", position: { x: 400, y: 140 }, data: { label: "Database" } },
  { id: "ext", position: { x: 250, y: 260 }, data: { label: "External integration" }, type: "output" },
];

const placeholderEdges: Edge[] = [
  { id: "e1", source: "app", target: "api" },
  { id: "e2", source: "api", target: "db" },
  { id: "e3", source: "api", target: "ext" },
];

export default function StructureMap() {
  return (
    <div style={{ height: "100%" }}>
      <ReactFlow nodes={placeholderNodes} edges={placeholderEdges} fitView>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
