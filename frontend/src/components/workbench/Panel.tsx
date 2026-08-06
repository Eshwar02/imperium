// Bottom panel — Problems / Output / Terminal / Run Events, VS Code style.
import { useWorkbench, type PanelTab } from "../../context/WorkbenchContext";
import { t } from "../../theme";
import FindingsPanel from "../panels/FindingsPanel";
import RunEventsPanel from "../panels/RunEventsPanel";
import Terminal from "./Terminal";
import Output from "./Output";

const TABS: { id: PanelTab; label: string }[] = [
  { id: "problems", label: "Problems" },
  { id: "output", label: "Output" },
  { id: "terminal", label: "Terminal" },
  { id: "runs", label: "Run Events" },
];

export default function Panel() {
  const { panelTab, setPanelTab, togglePanel } = useWorkbench();
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0,
      background: t.bgPanel, borderTop: `1px solid ${t.border}` }}>
      <div style={{ display: "flex", alignItems: "center", borderBottom: `1px solid ${t.border}`, flexShrink: 0 }}>
        {TABS.map((tab) => (
          <button key={tab.id} onClick={() => setPanelTab(tab.id)}
            style={{ padding: "6px 12px", fontSize: 11, letterSpacing: 0.5, textTransform: "uppercase",
              fontFamily: t.sans, cursor: "pointer", background: "transparent", border: "none",
              color: panelTab === tab.id ? t.text : t.textDim,
              borderBottom: panelTab === tab.id ? `1px solid ${t.text}` : "1px solid transparent" }}>
            {tab.label}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <div onClick={togglePanel} title="Close panel"
          style={{ padding: "4px 12px", cursor: "pointer", color: t.textDim, fontSize: 16 }}>×</div>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        {panelTab === "problems" && <FindingsPanel />}
        {panelTab === "output" && <Output />}
        {panelTab === "terminal" && <Terminal />}
        {panelTab === "runs" && <RunEventsPanel />}
      </div>
    </div>
  );
}
