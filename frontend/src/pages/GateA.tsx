import { useState } from "react";
import type { Category, GateDecision } from "../api/client";

// Gate A — pre-implementation, category-level approval (PRD §9 / TDD §7).
// Category-level gating deliberately prevents single bulk rubber-stamping.
// Foundation: static category list + decision toggles. TODO(team): load the real
// categorized to-do list from analysis findings; POST decisions via api.gateA.

const CATEGORIES: Category[] = ["security", "performance", "modernization", "integration", "documentation"];
const DECISIONS: GateDecision[] = ["approve", "reject", "defer"];

export default function GateA() {
  const [votes, setVotes] = useState<Record<Category, GateDecision>>({} as Record<Category, GateDecision>);

  return (
    <div style={{ padding: 24, fontFamily: "system-ui" }}>
      <h2>Gate A — Pre-Implementation</h2>
      <p style={{ color: "#666" }}>Approve, reject, or defer each category independently before any code is touched.</p>
      <table cellPadding={8}>
        <tbody>
          {CATEGORIES.map((cat) => (
            <tr key={cat}>
              <td style={{ textTransform: "capitalize", fontWeight: 600 }}>{cat}</td>
              {DECISIONS.map((d) => (
                <td key={d}>
                  <label>
                    <input
                      type="radio"
                      name={cat}
                      checked={votes[cat] === d}
                      onChange={() => setVotes((v) => ({ ...v, [cat]: d }))}
                    />{" "}
                    {d}
                  </label>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <button style={{ marginTop: 16 }} disabled>
        Submit decisions (wire to api.gateA)
      </button>
    </div>
  );
}
